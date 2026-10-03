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
| Runtime | Python 3.14 |
| Programming model | Azure Functions Python v2 (`function_app.py`) |
| SDK | `azure-cosmos`, `azure-identity` |
| JWT | `PyJWT[crypto]` による Entra ID トークン検証 |
| Lint / format | `ruff` |
| Type check | `mypy`。設定は `pyproject.toml` の `[tool.mypy]`。`jsonschema` の型は typeshed の `types-jsonschema` で補う |
| Seed validation | `jsonschema`。`scripts/seed_cosmos.py` の登録前検証だけで使うため、開発依存に置く |
| Test | `pytest` |
| Dependency locks | Python 3.14 向け `uv==0.12.19` の universal resolution。CI の Linux ジョブで再生成して同期を検査する。実行時は `functions/sdui_api/requirements.txt`、開発時はこれに `requirements-dev.txt` を追加 |
| CI package installer | `pip==26.1.2` (Linux / Windows)。Azure Functions remote build の pip はCIから制御しない |
| Auth pattern | Entra ID JWT validation via `auth.py` helpers |

## CI/CD

| 項目 | 内容 |
|---|---|
| Platform | GitHub Actions |
| Auth to Azure | Entra ID workload identity federation (OIDC) |
| PR | Terraform plan、lint、型チェック、test、依存固定ファイルの同期検査 |
| develop merge | dev auto deploy |
| Prod | manual approval |

## Agent Instruction Files

| ファイル | 役割 |
|---|---|
| `AGENTS.md` | Codexなどのエージェント向けの入口と地図 |
| `CLAUDE.md` | Claude Code向けの入口と地図 |
| `docs/*.md` | 実際の詳細ルール |

両入口ファイルは短く維持し、共通内容は手動で整合させてください。長い手順や領域別規約は `docs/` に置き、ディレクトリごとの `AGENTS.md` や `CLAUDE.md` は作成しません。
