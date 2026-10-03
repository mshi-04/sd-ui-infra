# インフラストラクチャ

この文書は、Terraform の構成と Azure リソースの変更手順を定義します。

## ディレクトリ

| パス | 役割 |
|---|---|
| `bootstrap/` | Terraform state 用の Storage Account と、CI用 federated credential |
| `modules/` | 再利用可能なモジュール |
| `envs/dev`, `envs/prod` | 環境ごとのルートモジュール |
| `environments/` | 環境ごとの変数ファイル |
| `config/app_roles.json` | app role と、role が付与する entitlement の正本 |

`bootstrap/` は state backend そのものを作るため、local state で1度だけ適用します。

ワークロード用のリソースグループと、CIが使う Entra ID アプリケーションも `bootstrap/` が管理します。
`envs/*` はリソースグループを `data` 参照します。

## モジュール

| モジュール | 管理対象 |
|---|---|
| `identity` | Entra ID の API app / client app、scope、app role |
| `ui_store` | Cosmos DB account、database、container |
| `observability` | Log Analytics workspace、Application Insights |
| `sdui_api` | Storage Account、Flex Consumption plan、Function App、role assignment |

モジュール内に `provider` ブロックと環境分岐を置きません。差異は `envs/*` から変数で渡します。

## 命名

リソース名は `{project_name}-{role}-{env}` を基本形にします。
グローバル一意かつハイフンを許可しない Storage Account のみ `{project_name}{role}{env}` の連結形とし、
`modules/sdui_api` 内で `replace()` により正規化します。

## 変更手順

1. `terraform fmt -recursive`
2. `terraform validate`
3. `terraform plan -var-file=../../environments/<env>.tfvars`
4. plan の差分を確認し、削除・置換が含まれる場合は理由を説明する
5. `terraform apply`

Entra ID のアプリケーション定義は組織のテナントに影響します。
`modules/identity` の変更を含む plan は、必ず差分を提示してから apply してください。

## 環境差分

| 項目 | dev | prod |
|---|---|---|
| Cosmos DB | serverless | serverless |
| Cosmos DB backup | Periodic（4時間間隔 / 8時間保持 / Local） | Continuous（7日） |
| リソース削除保護 | なし | なし |
| Function App のスケール上限 | 40 | 100 |
| ログ保持 | 30日 | 90日 |

Terraform は両環境とも削除保護を設定していません。`prevent_destroy` も管理ロックも定義していないため、`terraform destroy` と手動削除は止まりません。
保護が必要な場合は、運用者が `CanNotDelete` ロックをリソースグループへ手動で追加します。
CI用アプリケーションには、ワークロード用リソースグループの `Contributor` と条件付きの `Role Based Access Control Administrator` を付与しています。
`Contributor` は `Microsoft.Authorization` の書き込みを許可しないため、ロックの作成と削除は運用者が行います。

## 環境の撤去

撤去は、作成の逆順に行います。

1. `envs/prod` と `envs/dev` を、それぞれの tfvars を指定して `terraform destroy` する
2. `bootstrap/` を `terraform destroy` する

`envs/*` はリソースグループを `data` 参照するだけで、作成と削除は `bootstrap/` が担います。
`bootstrap/` を先に destroy すると、`envs/*` の state を保持する Storage Account が消え、`envs/*` を destroy できなくなります。
`bootstrap/` は local state のため、destroy が終わるまで state ファイルを保管します。

Application Insights は、リソースグループに `Application Insights Smart Detection` という action group を自動で作成します。
このリソースは Terraform の state に含まれず、リソースグループの削除を妨げます。
`bootstrap/` を destroy する前に、`envs/*` ごとに次のコマンドで削除します。

```bash
az monitor action-group delete -g <workload-resource-group> -n "Application Insights Smart Detection"
```

撤去後に再構築すると、Entra ID のアプリケーション登録には新しい client id が採番されます。
Android クライアント（sd-ui-app リポジトリ）の `gradle.properties` と MSAL 設定を、新しい output の値へ更新してください。
詳細は [docs/client_integration.md](client_integration.md) を参照してください。

テストユーザーは Terraform の管理対象外です。Entra ID 側に残るため、不要であれば手動で削除します。

## CI/CD

GitHub Actions は Entra ID の workload identity federation でサインインします。
federated credential は `bootstrap/` が作成し、subject は `pull_request` と `environment:<env>` です。

### ワークフローの運用方針

- OIDC トークン (`id-token: write`) は Azure へサインインするジョブだけに付与します。workflow 全体の権限は `contents: read` です。CD は reusable workflow を呼ぶ側のジョブにも同じ権限を付けます。呼ばれる側は呼び出し側の権限を超えられないためです。
- CI は同じ ref の古い実行を取り消します。CD は実行中の apply を取り消さず、同じ ref の実行を順番に待たせます。
- 各ジョブに `timeout-minutes` を設定します。CI は python 15分、terraform-validate 10分、terraform-plan 15分、CD の deploy は30分です。
- `uses:` は同じメジャーバージョンの最新リリースのコミット SHA で固定し、行末のコメントにリリースタグを残します。更新は Dependabot が行います。
- Linux の python ジョブで `uv==0.12.19` により固定ファイルを入力から再生成し、差分があれば失敗させます。手順は [コマンド](commands.md) の依存固定を参照してください。
- Dependabot は github-actions、terraform (`envs/dev`、`envs/prod`、`bootstrap`)、pip (`functions/sdui_api`、ルートの開発依存) を週次で確認します。

`.tfvars` はコミットしないため、CI では変数を GitHub Actions variables から渡します。

| variable | スコープ | 用途 |
|---|---|---|
| `AZURE_CLIENT_ID` | repository | CI用アプリケーションの client id |
| `AZURE_TENANT_ID` | repository | テナントID |
| `AZURE_SUBSCRIPTION_ID` | repository | サブスクリプションID |
| `TFSTATE_RESOURCE_GROUP_NAME` | repository | state 用リソースグループ名 |
| `TFSTATE_STORAGE_ACCOUNT_NAME` | repository | state 用 Storage Account 名 |
| `DEV_PUBLIC_CLIENT_REDIRECT_URIS` / `DEV_ALLOWED_ORIGINS` | repository | PR時の dev plan に使う値 |
| `DEV_APP_ROLE_ASSIGNMENTS` / `DEV_PRE_AUTHORIZED_CLIENT_IDS` | repository | PR時の dev plan に使う role 割り当てと事前承認クライアント |
| `PUBLIC_CLIENT_REDIRECT_URIS` / `ALLOWED_ORIGINS` | environment (`dev`, `prod`) | 環境ごとのクライアント設定 |
| `APP_ROLE_ASSIGNMENTS` / `PRE_AUTHORIZED_CLIENT_IDS` | environment (`dev`, `prod`) | 環境ごとの role 割り当てと事前承認クライアント |

リスト型の variable は `["https://app.example.com"]` の形式で登録します。
`APP_ROLE_ASSIGNMENTS` は `{"<object-id>":["BillingViewer"]}` の形式、`PRE_AUTHORIZED_CLIENT_IDS` はリスト型の形式で登録します。
値はローカルの tfvars と一致させます。CD の apply が差分として割り当てと事前承認を削除するためです。
割り当てるものがない場合も `{}` / `[]` を登録します。
未登録の variable は空文字として渡され、Terraform が値を解釈できず plan が失敗します。既定値では実行されません。
`prod` の GitHub Environment には required reviewers を設定し、手動承認を必須にします。
