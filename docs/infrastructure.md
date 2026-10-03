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
| リソース削除保護 | 無効 | 有効 |
| Function App のスケール上限 | 40 | 100 |
| ログ保持 | 30日 | 90日 |

## CI/CD

GitHub Actions は Entra ID の workload identity federation でサインインします。
federated credential は `bootstrap/` が作成し、subject は `pull_request` と `environment:<env>` です。

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
