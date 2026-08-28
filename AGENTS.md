# AGENTS.md

このリポジトリのAI作業ルールです。詳細は [docs/](docs/) の該当文書を参照してください。
ここは作業時の地図として役割をします。

## 主要文書

- [docs/tech_stack.md](docs/tech_stack.md): 技術スタック
- [docs/architecture.md](docs/architecture.md): サーバー駆動UIの構成、UIスキーマ、解決フロー
- [docs/auth.md](docs/auth.md): Entra ID のアプリ構成、トークン検証、ログ衛生
- [docs/infrastructure.md](docs/infrastructure.md): envs / modules 構成、Terraform の変更手順
- [docs/coding_standards.md](docs/coding_standards.md): Terraform / Python / ドキュメントの規約
- [docs/commands.md](docs/commands.md): よく使うコマンド
- [docs/testing.md](docs/testing.md): pytest のテスト構成と方針

## 作業の前提

- `modules/identity` の変更はテナント全体へ影響します。plan の差分を提示してから apply します。
- シークレット、テナントID、サブスクリプションIDをコードとドキュメントに含めません。
- ブランチは `develop` から切り、`main` へは `develop` 経由で入れます。
