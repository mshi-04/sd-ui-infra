# CLAUDE.md

このリポジトリのAI作業ルールです。詳細は [docs/](docs/) の該当文書を参照してください。
ここは作業時の地図として役割をします。

## 主要文書

- [docs/getting_started.md](docs/getting_started.md): テナント準備から dev 環境が動くまでの順序
- [docs/tech_stack.md](docs/tech_stack.md): 技術スタック
- [docs/architecture.md](docs/architecture.md): サーバー駆動UIの構成、UIスキーマ、解決フロー
- [docs/auth.md](docs/auth.md): Entra ID のアプリ構成、トークン検証、ログ衛生
- [docs/client_integration.md](docs/client_integration.md): Android クライアントとのAPI契約、MSAL設定、モックサーバー
- [docs/infrastructure.md](docs/infrastructure.md): envs / modules 構成、Terraform の変更手順
- [docs/coding_standards.md](docs/coding_standards.md): Terraform / Python / ドキュメントの規約
- [docs/commands.md](docs/commands.md): よく使うコマンド
- [docs/testing.md](docs/testing.md): pytest のテスト構成と方針

## AI skills

作業内容に応じて [.claude/skills/](.claude/skills/) の該当 `SKILL.md` を読みます。

- [ui-definition-implementation](.claude/skills/ui-definition-implementation/SKILL.md): UI surface と UI 定義（seed、version、variant、requiredEntitlements）の設計・実装・修正
- [app-role-implementation](.claude/skills/app-role-implementation/SKILL.md): app role と entitlement（config/app_roles.json と Entra ID の app role）の設計・実装・修正
- [api-implementation](.claude/skills/api-implementation/SKILL.md): Azure Functions の HTTP API と API 契約の設計・実装・修正
- [infra-implementation](.claude/skills/infra-implementation/SKILL.md): Terraform / Azure インフラの設計・実装・修正

## 作業の前提

- `modules/identity` の変更はテナント全体へ影響します。plan の差分を提示してから apply します。
- シークレット、テナントID、サブスクリプションIDをコードとドキュメントに含めません。
- ブランチは `develop` から切り、`main` へは `develop` 経由で入れます。
