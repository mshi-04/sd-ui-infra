# sd-ui-infra

日本語 | [English](README.en.md)

Azure 上のサーバー駆動UI（Server-Driven UI）基盤を、学習・参照用に保存したサンプルです。
Microsoft Entra ID で認証したユーザーのロールとアカウント設定に応じて、Android アプリへ配信するUIスキーマを組み立てます。
対応するクライアントは [sd-ui-app](https://github.com/mshi-04/sd-ui-app) です。

保存時点の実装を参照するためのリポジトリで、継続保守や元のクラウド環境の稼働は前提にしていません。
Azure なしでAPIを試す手順と、自分の Azure 環境を構築するための詳細文書を収録しています。

詳細文書には開発当時の環境を前提とした記録も含まれます。公開版の設定値はサンプルとして、ご自身の環境に合わせて読み替えてください。

## 実装していること

- Azure Functions / Python の `GET /api/ui/{surface}`。同梱のUI定義は `dashboard` です。
- Microsoft Entra ID の access token を検証し、署名・issuer・audience・`UiSchema.Read` scope を確認します。
- Cosmos DB からUI定義とアカウントプロファイルを取得し、`version` の文字列比較で最新の定義を選びます。
- app role と profile の audience に応じた variant を重ね、entitlement が足りない component を除外します。profile の theme・density・表示順の固定も反映します。
- 解決済みスキーマから `ETag` を生成し、`If-None-Match` が完全一致すれば `304` を返します。本番APIの `200` / `304` は `Cache-Control: private, max-age=60`（既定値）と `Vary: Authorization` を伴います。
- Terraform で dev / prod の Azure Functions、Cosmos DB、認証、監視基盤を定義します。

本番APIの応答は次のとおりです。詳細は [クライアント連携](docs/client_integration.md) を参照してください。

| ステータス | 内容 |
|---|---|
| `200` / `304` | UIスキーマを返す / キャッシュと一致し本文を返さない |
| `401` | トークンが無効、または必要な scope がない |
| `404` | 対象 surface の定義がない |
| `500` | 設定・保存データの不備、恒常的な依存先の失敗、想定外の不具合 |
| `503` | JWKS または Cosmos DB の一時的な障害 |

## Azure なしでAPIを試す

前提は Python 3.14 です。以下はリポジトリのルートで実行します。
モックサーバーは同梱の seed と本番と共通の resolver を使い、Azure アカウント、Terraform、Azure Functions Core Tools を必要としません。
依存パッケージのインストールにはインターネット接続が必要です。

Windows / PowerShell:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install pip==26.1.2
.venv\Scripts\python -m pip install -r functions/sdui_api/requirements.txt -r requirements-dev.txt
.venv\Scripts\python scripts/seed_cosmos.py --dry-run
.venv\Scripts\python scripts/dev_server.py --port 8080
```

Linux:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install pip==26.1.2
.venv/bin/python -m pip install -r functions/sdui_api/requirements.txt -r requirements-dev.txt
.venv/bin/python scripts/seed_cosmos.py --dry-run
.venv/bin/python scripts/dev_server.py --port 8080
```

`--dry-run` は seed を検証するだけで、Azure への接続やデータの書き込みを行いません。
サーバーが起動したら、別のターミナルで次を実行します。

Windows / PowerShell:

```powershell
curl.exe -i http://127.0.0.1:8080/api/ui/dashboard
curl.exe -i -H "X-Dev-Roles: SupportAgent" http://127.0.0.1:8080/api/ui/dashboard
```

Linux:

```bash
curl -i http://127.0.0.1:8080/api/ui/dashboard
curl -i -H "X-Dev-Roles: SupportAgent" http://127.0.0.1:8080/api/ui/dashboard
```

同梱の seed では、ヘッダーなしの応答に `usage-summary` が含まれます。
`SupportAgent` を指定すると、`usage-summary` のタイトルが変わり、`impersonation-banner` が追加されます。
`X-Dev-Oid` で seed 内の profile を選ぶこともできます。サーバーは `127.0.0.1` に待ち受け、`Ctrl+C` で停止します。

モックはトークン検証を省略し、`X-Dev-Oid` / `X-Dev-Roles` を利用者情報として扱います。
本番の認証・外部サービス障害の処理は再現せず、`Vary: Authorization` など一部のヘッダーも本番と異なります。開発用途で利用してください。

### Android アプリから接続する場合

Android エミュレーターからの base URL は `http://10.0.2.2:8080/api/` です。
アプリの接続設定は [sd-ui-app](https://github.com/mshi-04/sd-ui-app) を参照してください。
モックへ接続する場合も、アプリでダッシュボードを開くには MSAL の設定とサインインが必要です。
アプリは `X-Dev-*` ヘッダーを送らないため、モックでは匿名ユーザーとして応答されます。
このAPIのローカル実行だけで、アプリ全体を Azure なしで動かせるわけではありません。

## 自分の Azure 環境へ構築する

Azure サブスクリプションと Entra ID テナント、Azure CLI、`.terraform-version` に示した Terraform、Azure Functions Core Tools が必要です。
初期構築にはサブスクリプションのロール割り当てと Entra ID のアプリ・権限を管理できる権限も必要です。

[セットアップ](docs/getting_started.md) の順序に従い、state backend とデプロイ用 ID の作成、環境設定、リソースの適用、Cosmos DB への seed 投入、クライアント設定を行います。
`environments/*.tfvars.example` と `functions/sdui_api/local.settings.json.example` は設定のひな形です。自分の環境の値を使い、実設定や資格情報をコミットしないでください。
GitHub Actions にも Azure の plan / deploy 処理が含まれ、実行には自分の環境に合わせた OIDC と変数の設定が必要です。
権限・CI/CD・撤去の詳細は [インフラストラクチャ](docs/infrastructure.md)、認証の詳細は [認証](docs/auth.md) を参照してください。

## 検証

上の手順で作成した仮想環境を使います。Python の検証と seed の dry-run は Azure へのログインを必要としません。

Windows / PowerShell:

```powershell
.venv\Scripts\python -m pip check
.venv\Scripts\python -m ruff format --check functions scripts
.venv\Scripts\python -m ruff check functions scripts
.venv\Scripts\python -m mypy
.venv\Scripts\python -m pytest
.venv\Scripts\python scripts/seed_cosmos.py --dry-run
```

Linux:

```bash
.venv/bin/python -m pip check
.venv/bin/python -m ruff format --check functions scripts
.venv/bin/python -m ruff check functions scripts
.venv/bin/python -m mypy
.venv/bin/python -m pytest
.venv/bin/python scripts/seed_cosmos.py --dry-run
```

Terraform は、backend に接続せずに次の検証ができます。初回の provider 取得にはインターネット接続が必要です。

```bash
terraform fmt -check -recursive
terraform -chdir=envs/dev init -backend=false
terraform -chdir=envs/dev validate
terraform -chdir=envs/prod init -backend=false
terraform -chdir=envs/prod validate
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
```

pytest は Cosmos DB と JWKS への通信を差し替えます。実クラウド上の動作や Functions ホスト経由のHTTP通信を検証するものではありません。
`terraform validate` も実環境への適用結果を保証しません。詳細は [テスト](docs/testing.md) と [コマンド](docs/commands.md) を参照してください。

## 構成

| パス | 役割 |
|---|---|
| `bootstrap/` | Terraform state backend、環境ごとのデプロイ用 ID、PR の plan 用 ID の初期構築 |
| `modules/` | 再利用可能な Terraform モジュール |
| `envs/` | dev / prod のルートモジュール |
| `environments/` | 環境設定のひな形 |
| `config/` | app role と entitlement の定義 |
| `functions/sdui_api/` | UIスキーマ配信APIとテスト |
| `seed/` | UI定義、アカウントプロファイル、保存文書の JSON Schema |
| `scripts/` | ローカルモック、seed 検証・投入スクリプト |
| `docs/` | 構成、API契約、セットアップ、開発規約 |
| `.github/workflows/` | Python / Terraform の検証と Azure デプロイの定義 |

## 制約

- 同梱する画面は `dashboard` です。業務データAPIや、component の `action` を実行する機能は提供しません。
- Android クライアントが描画できる component の種類と `props` の形には制約があります。詳細は [クライアント連携](docs/client_integration.md) とクライアント側の文書を確認してください。
- `If-None-Match` は文字列の完全一致で判定します。弱い ETag、複数値、`*` の一般的な照合には対応していません。
- 保存時点の依存関係・クラウド構成です。現在のサービスやツールで利用する際は、互換性と必要な設定を確認してください。

## ドキュメント

詳細文書は日本語です。

- [セットアップ](docs/getting_started.md)
- [技術スタック](docs/tech_stack.md)
- [アーキテクチャ](docs/architecture.md)
- [認証](docs/auth.md)
- [クライアント連携](docs/client_integration.md)
- [インフラストラクチャ](docs/infrastructure.md)
- [コーディング規約](docs/coding_standards.md)
- [コマンド](docs/commands.md)
- [テスト](docs/testing.md)
