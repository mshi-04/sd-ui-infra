# インフラストラクチャ

この文書は、Terraform の構成と Azure リソースの変更手順を定義します。

## ディレクトリ

| パス | 役割 |
|---|---|
| `bootstrap/` | Terraform state 用の Storage Account と、環境ごとのデプロイ用 ID、PR の plan 用 ID |
| `modules/` | 再利用可能なモジュール |
| `envs/dev`, `envs/prod` | 環境ごとのルートモジュール |
| `environments/` | 環境ごとの変数ファイル |
| `config/app_roles.json` | app role と、role が付与する entitlement の正本 |

`bootstrap/` は state backend そのものを作るため、local state で1度だけ適用します。

ワークロード用のリソースグループ、GitHub Actions が使う Entra ID アプリケーション、リソースプロバイダーの登録も `bootstrap/` が管理します。
`envs/*` はリソースグループを `data` 参照します。

## Identity の構成

GitHub Actions のサインインに使う ID は、権限の異なる2種類に分けます。
どちらも `bootstrap/` が作成し、実行者はサブスクリプションの `Owner` です。

| ID | federated credential の subject | Azure RBAC | Microsoft Graph |
|---|---|---|---|
| `{project_name}-deploy-{env}`（環境ごと） | `repo:<owner>/<name>:environment:<env>` | 自環境のワークロード用リソースグループに `Contributor` と条件付きの `Role Based Access Control Administrator`。自環境の state コンテナに `Storage Blob Data Contributor` | `Application.ReadWrite.OwnedBy` |
| `{project_name}-plan`（1つ） | `repo:<owner>/<name>:pull_request` | dev のワークロード用リソースグループに `Reader`。dev の state コンテナに `Storage Blob Data Reader` | なし |

- deploy ID は、その環境の GitHub Environment に紐づくジョブだけがサインインできます。dev の deploy ID は prod のリソースグループと state に触れません。
- `Role Based Access Control Administrator` には、割り当て可能なロールを `ci_assignable_role_definition_ids`（既定は `Storage Blob Data Owner` と `Storage Blob Data Contributor`）に限る条件を付けています。
- plan ID は読み取り専用で、PR のコードが実行されても書き込みはできません。prod のリソースと prod の state にも到達できません。

### Entra ID アプリ登録の owner

`modules/identity` が作る API app と client app は、環境の deploy ID（サービスプリンシパル）を owner にします。
`Application.ReadWrite.OwnedBy` は owner になっているアプリだけを管理できる権限のため、`envs/*` の `app_owner_object_id` に、その環境の deploy サービスプリンシパルの object id を渡します。
値は `bootstrap/` の出力 `deploy_service_principal_object_ids` から取得します。
operator が手元から apply する場合も同じ値を渡し、owner が operator と CI で入れ替わらないようにします。

ユーザーへの app role の割り当ては Terraform では管理しません。
割り当てには Microsoft Graph の `AppRoleAssignment.ReadWrite.All` が必要で、この権限はテナント全体の権限昇格に使えるためです。
割り当ては Entra 管理センターまたは CLI で operator が行います。

### State コンテナ

state は環境ごとのコンテナ `tfstate-dev` と `tfstate-prod` に分けます。
同じ Storage Account に置きますが、各 ID の `Storage Blob Data` ロールはコンテナ単位です。
そのため、plan ID と dev の deploy ID は prod の state を読めません。
operator には Storage Account 全体の `Storage Blob Data Owner` を付与します。

### Resource provider の登録

`envs/*` の azurerm provider は `resource_provider_registrations = "none"` とします。
deploy ID はサブスクリプションスコープの権限を持たず、自動登録できないためです。
必要な resource provider は `bootstrap/` が `resource_providers_to_register` で登録します。
`envs/*` で新しい種類のリソースを使うときは、先に `bootstrap/` の一覧へ追加して apply します。

## モジュール

| モジュール | 管理対象 |
|---|---|
| `identity` | Entra ID の API app / client app、scope、app role |
| `ui_store` | Cosmos DB account、database、container |
| `observability` | Log Analytics workspace、Application Insights、API 5xx アラート（通知先設定時のみ） |
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
| API 5xx アラート | なし | 通知先設定時に有効（5分間に5件超でメール通知。閾値は未検証） |

Terraform は両環境とも削除保護を設定していません。`prevent_destroy` も管理ロックも定義していないため、`terraform destroy` と手動削除は止まりません。
保護が必要な場合は、運用者が `CanNotDelete` ロックをリソースグループへ手動で追加します。
デプロイ用 ID には、自環境のワークロード用リソースグループの `Contributor` と条件付きの `Role Based Access Control Administrator` を付与しています。
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
federated credential は `bootstrap/` が作成します。

| 用途 | subject | ID |
|---|---|---|
| PR の plan | `pull_request` | plan ID |
| dev の CD | `environment:dev` | dev の deploy ID |
| prod の CD | `environment:prod` | prod の deploy ID |

PR のジョブは GitHub Environment を宣言しないでください。
宣言すると `environment:<env>` の subject が発行され、deploy ID でサインインできてしまいます。

### 必要な GitHub の設定

- GitHub Environment は `dev` と `prod` を作成します。
- deployment branch policy は、`dev` を `develop`、`prod` を `main` に限定します。これにより、PR のブランチから deploy ID の subject を得られなくなります。
- `develop` と `main` は直接 push を禁止し、PR 経由に限定します。
- `prod` には required reviewers を設定します。private リポジトリで required reviewers を使うには GitHub Enterprise が必要です。使えない場合は、branch の保護と deployment branch policy で代替し、承認の欠如を運用上のリスクとして認識してください。

### PR の plan

PR の plan は plan ID で `-refresh=false` を付けて実行します。実リソースの drift は表示されません。
drift の確認は operator が手元で行います。

plan ID は dev の state を読めます。
Function App の SCM basic 認証、Storage のキー認証、Cosmos DB のローカル認証をすべて無効にしているため、state に残る資格情報は使えません。
この前提を崩す変更（いずれかの認証を有効にする変更）は、plan ID から state が読める点を踏まえてレビューしてください。

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
| `AZURE_PLAN_CLIENT_ID` | repository | plan ID の client id |
| `AZURE_TENANT_ID` | repository | テナントID |
| `AZURE_SUBSCRIPTION_ID` | repository | サブスクリプションID |
| `TFSTATE_RESOURCE_GROUP_NAME` | repository | state 用リソースグループ名 |
| `TFSTATE_STORAGE_ACCOUNT_NAME` | repository | state 用 Storage Account 名 |
| `DEV_APP_OWNER_OBJECT_ID` | repository | PR時の dev plan に使う、dev の deploy サービスプリンシパルの object id |
| `DEV_PUBLIC_CLIENT_REDIRECT_URIS` / `DEV_ALLOWED_ORIGINS` | repository | PR時の dev plan に使う値 |
| `DEV_PRE_AUTHORIZED_CLIENT_IDS` | repository | PR時の dev plan に使う事前承認クライアント |
| `AZURE_CLIENT_ID` | environment (`dev`, `prod`) | その環境の deploy ID の client id |
| `APP_OWNER_OBJECT_ID` | environment (`dev`, `prod`) | その環境の deploy サービスプリンシパルの object id |
| `PUBLIC_CLIENT_REDIRECT_URIS` / `ALLOWED_ORIGINS` | environment (`dev`, `prod`) | 環境ごとのクライアント設定 |
| `PRE_AUTHORIZED_CLIENT_IDS` | environment (`dev`, `prod`) | 環境ごとの事前承認クライアント |
| `ALERT_EMAIL_ADDRESSES` | environment (`prod`) | 5xx アラートの通知先メールアドレスの JSON 配列。未設定ならアラートなし |

`AZURE_CLIENT_ID` は repository スコープに登録しません。
登録すると、environment スコープの設定漏れが repository の値で隠れ、意図しない ID でサインインします。

リスト型の variable は `["https://app.example.com"]` の形式で登録します。
`PRE_AUTHORIZED_CLIENT_IDS` もリスト型の形式で登録します。
値はローカルの tfvars と一致させます。CD の apply が差分として事前承認を削除するためです。
事前承認するものがない場合も `[]` を登録します。
未登録の variable は空文字として渡され、Terraform が値を解釈できず plan が失敗します。既定値では実行されません。
`prod` の GitHub Environment には required reviewers を設定し、手動承認を必須にします。

## 再構築の確認項目

`bootstrap/` を適用し直したあと、次を確認します。

1. 出力に deploy の client id が2つ（dev、prod）、plan の client id が1つ、state コンテナが2つ（`tfstate-dev`、`tfstate-prod`）あること
2. Microsoft Graph の `Application.ReadWrite.OwnedBy` が deploy の2つのサービスプリンシパルにだけ付与されていること。plan ID には Graph の権限がないこと
3. RBAC のスコープと federated credential の subject が上の表のとおりであること
4. resource provider が登録されていること
5. 最初の dev の CD が成功し、API app と client app の owner が dev の deploy サービスプリンシパルであること
6. PR の plan が成功し、owner の差分が出ないこと
7. 否定テスト: PR のジョブから `tfstate-prod` と `prod` の GitHub Environment に到達できないこと
8. Function App の SCM basic 認証が無効であること。`basicPublishingCredentialsPolicies/scm` の `allow` が `false` になる
