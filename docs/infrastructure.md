# インフラストラクチャ

この文書は、Terraform の構成と Azure リソースの変更手順を定義します。

## ディレクトリ

| パス | 役割 |
|---|---|
| `bootstrap/` | Terraform state 用の Storage Account と、CI用 federated credential |
| `modules/` | 再利用可能なモジュール |
| `envs/dev`, `envs/prod` | 環境ごとのルートモジュール |
| `environments/` | 環境ごとの変数ファイル |

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
| Cosmos DB backup | Periodic (8時間) | Continuous (7日) |
| リソース削除保護 | 無効 | 有効 |
| Function App のスケール上限 | 40 | 100 |
| ログ保持 | 30日 | 90日 |
