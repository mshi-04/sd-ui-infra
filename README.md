# sd-ui-infra

Azure 上に構築するサーバー駆動UI（Server-Driven UI）基盤です。
Microsoft Entra ID で認証したユーザーのアカウント属性に応じて、配信するUIスキーマを出し分けます。

## 構成

| パス | 役割 |
|---|---|
| `bootstrap/` | Terraform state backend の初期構築 |
| `modules/` | 再利用可能な Terraform モジュール |
| `envs/` | 環境ごとのルートモジュール |
| `environments/` | 環境ごとの変数ファイル |
| `functions/sdui_api/` | UIスキーマ配信API（Azure Functions / Python） |
| `docs/` | 技術スタック、アーキテクチャ、規約 |

## ドキュメント

- [docs/tech_stack.md](docs/tech_stack.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/auth.md](docs/auth.md)
- [docs/infrastructure.md](docs/infrastructure.md)
- [docs/coding_standards.md](docs/coding_standards.md)
- [docs/commands.md](docs/commands.md)
- [docs/testing.md](docs/testing.md)
