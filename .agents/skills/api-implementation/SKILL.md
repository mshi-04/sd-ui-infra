---
name: api-implementation
description: Azure Functions の HTTP API（functions/sdui_api の route / 認証 / 応答 / payload / 設定 / Cosmos DB 呼び出し / resolver、ETag とキャッシュヘッダー、scripts/dev_server.py）と API 契約の設計・実装・修正に使う。401/404/500/503 の分類、ログ衛生、環境変数と契約の同期手順を提供。
---

# API Implementation

## 実装手順

1. 変更が route 追加 / 認証 / 外部サービス呼び出し / payload / 設定 / キャッシュのどれに当たるかを分ける。route 追加は 2〜4 と 8、外部呼び出しは 3 と 9、payload は 4 と 8、設定は 6 と 7 を中心に進める。
2. `functions/sdui_api/function_app.py` の `get_ui_schema` と `_serve` を確認する。順序は 設定読込（`load_settings`）→ 認証（`extract_bearer_token` / `verify_token`）→ リポジトリ（`fetch_latest_definition` / `fetch_profile`）→ `resolve` → 応答。この順序を崩さない。
3. 入口に分類を足さない。SDK の例外は `ui_repository.py`（Cosmos DB）と `auth.py`（JWKS）で `dependency_errors.py` の `DependencyUnavailableError`（一時障害、503）か `DependencyFailureError`（恒常的、500）へ変換し、`function_app.py` に SDK の型を持ち込まない。新しい問い合わせの足し方は `references/request-flow.md` を参照する。
4. 応答は `response.py` の `json_response` / `error_response` / `not_modified` / `cache_headers` だけで作る。エラー本文は `{"error": {"code": ...}}` のみで、失敗理由や例外の内容を載せない。
5. ログに access token、`upn`、`email`、氏名を出さない。`oid` は `auth.mask_subject` を通す。外部障害は依存先名と例外の型・status だけ、設定不備は変数名と `missing` / `invalid` だけを残す。
6. 環境変数は `settings.py`、`local.settings.json.example`、`modules/sdui_api/main.tf` と `envs/*/main.tf`、`tests/conftest.py` を同時に変える（`references/change-checklist.md`）。Terraform 側は `infra-implementation` を参照する。
7. 新しい scope は `modules/identity`（テナント全体へ影響する）を変え、`REQUIRED_SCOPE` と `docs/auth.md` を合わせる。承認と plan の扱いは `infra-implementation` を参照する。app role は `app-role-implementation`、UI 定義に持たせる設定は `ui-definition-implementation` を参照する。
8. payload は `models.py` の `to_payload`、`ui_resolver.etag_of` への影響、`docs/client_integration.md` を同じ変更で更新する。`scripts/dev_server.py` は独自の分岐を持つ箇所だけ追従する。契約が変わる場合は `sd-ui-app`（Android）へ通知する。アプリは未知のキーを無視するためフィールドの追加は互換だが、削除・改名はアプリの対応を先に済ませる。ETag は payload の hash なので、リクエストごとに変わる値を payload に入れない。
9. タイムアウトと再試行（`ui_repository.py` の `COSMOS_*`、`auth.py` の `JWKS_*`）は緩めない。変える場合は `docs/architecture.md` の表も更新する。
10. 型は mypy strict で通す。`cast()` で警告を消さず、`# type: ignore[<code>]` はエラーコード付きで書く。動作を変えたら `functions/sdui_api/tests/` に、変更の種類ごとのテストを同じ変更で足す。

## 検証手順

1. `.venv\Scripts\python -m ruff format --check functions scripts`
2. `.venv\Scripts\python -m ruff check functions scripts`
3. `.venv\Scripts\python -m mypy`（引数なし）
4. `.venv\Scripts\python -m pytest`（個別実行は `-k` かファイルパス。dev mock は `-k dev_server`）
5. payload や seed に触れた場合は `.venv\Scripts\python scripts/seed_cosmos.py --dry-run`。契約を変えた場合は `docs/client_integration.md` のモックサーバー手順で手動確認する。
6. Terraform を変えた場合は `terraform fmt -check -recursive` と、変更した `envs/dev` / `envs/prod` / `bootstrap` ごとの `terraform -chdir=<dir> init -backend=false` に続く `validate`。CI は 3 つとも検証し、新しい変数に default が無いと `envs/prod` が壊れる。
7. 承認が必要な操作は `terraform apply`、`modules/identity` を含む plan、削除・置換・destroy を含む plan、`bootstrap/` の変更、Cosmos DB への実書き込み。差分を示し、`develop` / `main` へのマージ前（CD の apply）も含めて、ユーザーの承認を得てから行う（`infra-implementation`）。

## 参考資料

- [references/request-flow.md](references/request-flow.md): 入口の骨格、失敗の分類表、問い合わせの足し方、キャッシュヘッダー、scope と roles、ログ衛生
- [references/change-checklist.md](references/change-checklist.md): ルート・環境変数・scope・payload・キャッシュ設定を変えるときの同期先、テストの書き方、型の規則
- [docs/architecture.md](../../../docs/architecture.md)
- [docs/auth.md](../../../docs/auth.md)
- [docs/client_integration.md](../../../docs/client_integration.md)
- [docs/testing.md](../../../docs/testing.md)
- [docs/coding_standards.md](../../../docs/coding_standards.md)
- [docs/commands.md](../../../docs/commands.md)
