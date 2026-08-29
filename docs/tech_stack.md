# 技術スタック

この文書は、リポジトリで前提にする技術と運用ツールをまとめます。

## Infrastructure

| 項目 | 内容 |
|---|---|
| Cloud | Azure |
| Region | `japaneast` |
| IaC | Terraform |
| Root modules | `envs/dev`, `envs/prod` |
| Reusable modules | `modules/` |
| Bootstrap | `bootstrap/` |
| 変数ファイル | `environments/dev.tfvars`, `environments/prod.tfvars` |

## Azure Services

| カテゴリ | サービス | 用途 |
|---|---|---|
| Auth | Microsoft Entra ID | ユーザー認証、app role によるUI出し分けの入力 |
| Client | Android (Kotlin / Compose) | 別リポジトリ `sd-ui-app`。MSAL Android でサインインする |
| Compute | Azure Functions (Flex Consumption) | UIスキーマ配信API |
| Database | Azure Cosmos DB for NoSQL (serverless) | UI定義、アカウントプロファイル |
| Storage | Azure Storage Account | Functions のデプロイコンテナ、Terraform state |
| Security | Microsoft Entra ID, Managed Identity, RBAC | 権限、データプレーン認可 |
| Observability | Log Analytics, Application Insights | ログ、分散トレース、メトリクス |

## Terraform

| 項目 | 内容 |
|---|---|
| Version | `.terraform-version` を参照 |
| Provider | `hashicorp/azurerm`, `hashicorp/azuread` |
| State | Azure Storage backend |
| Locking | Blob lease による backend 標準ロック |
| Formatting | `terraform fmt -recursive` |
| Validation | `terraform validate`, `terraform plan` |

## Functions

| 項目 | 内容 |
|---|---|
| Runtime | Python 3.12 |
| Programming model | Azure Functions Python v2 (`function_app.py`) |
| SDK | `azure-cosmos`, `azure-identity` |
| JWT | `PyJWT[crypto]` による Entra ID トークン検証 |
| Lint / format | `ruff` |
| Test | `pytest` |
| Auth pattern | Entra ID JWT validation via `auth.py` helpers |

## CI/CD

| 項目 | 内容 |
|---|---|
| Platform | GitHub Actions |
| Auth to Azure | Entra ID workload identity federation (OIDC) |
| PR | Terraform plan、lint、test |
| develop merge | dev auto deploy |
| Prod | manual approval |

## Agent Instruction Files

| ファイル | 役割 |
|---|---|
| `AGENTS.md` | Codexなどのエージェント向けの入口と地図 |
| `CLAUDE.md` | Claude Code向けの入口と地図 |
| `docs/*.md` | 実際の詳細ルール |

両入口ファイルは短く維持し、共通内容は手動で整合させてください。長い手順や領域別規約は `docs/` に置き、ディレクトリごとの `AGENTS.md` や `CLAUDE.md` は作成しません。
