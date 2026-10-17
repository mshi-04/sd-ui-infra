# 変更時の同期先とテスト

API の変更で、一緒に更新するファイルと確認事項をまとめます。

## 環境変数を足す・変える

`settings.py` の `load_settings` が正本です。現在の変数は次のとおりです。

| 変数 | 必須 | 既定 / 備考 |
|---|---|---|
| `ENTRA_TENANT_ID` | 必須 | `issuer` と `jwks_uri` の組み立てに使う |
| `ENTRA_API_CLIENT_ID` | 必須 | `aud` の検証値 |
| `REQUIRED_SCOPE` | 任意 | 既定 `UiSchema.Read` |
| `COSMOS_ENDPOINT` | 必須 | |
| `COSMOS_DATABASE` | 必須 | |
| `UI_DEFINITIONS_CONTAINER` | 必須 | |
| `ACCOUNT_PROFILES_CONTAINER` | 必須 | |
| `UI_CACHE_MAX_AGE_SECONDS` | 任意 | 既定 60。整数でなければ `SettingsError(..., "invalid")` |
| `ROLE_ENTITLEMENTS` | 任意 | 既定 `{}`。JSON で role から entitlement 配列への対応 |

更新する場所は次の6つです。

| 場所 | 内容 |
|---|---|
| `envs/dev/main.tf` / `envs/prod/main.tf` | `module "sdui_api"` に変数を渡す。default を持たない変数は両方に足す |
| `functions/sdui_api/settings.py` | `Settings` にフィールドを足し、`_required` か `_parsed` で読む。値を含むメッセージを例外に入れない |
| `functions/sdui_api/local.settings.json.example` | 実値でなくダミー値を足す。テナントIDやサブスクリプションIDを書かない |
| `modules/sdui_api/main.tf` の `app_settings` | 同名のキーを足し、`variables.tf` に変数を追加する。`infra-implementation` を参照する |
| `functions/sdui_api/tests/conftest.py` | `REQUIRED_ENVIRONMENT` か `OPTIONAL_ENVIRONMENT` に足す |

Terraform の変更は `terraform apply` の承認が必要です（`infra-implementation` を参照）。

`settings_environment` fixture が両方の一覧の変数を消してから必須分を設定し直し、`load_settings.cache_clear()` を呼びます。
一覧に足し忘れると、テストが実行環境の値に依存します。

`role_entitlements` は `config/app_roles.json` を `envs/*` が読んで渡します。role の追加は `app-role-implementation` を参照します。

## scope を足す

- scope の定義は `modules/identity`（`oauth2_permission_scope`）にあり、`modules/identity` の変更はテナント全体へ影響します。
  plan の差分を提示してから apply します。
- API 側は `REQUIRED_SCOPE` と `auth.verify_token` の `required_scope` で検証します。
  `envs/*` は `module.identity.ui_schema_read_scope` を `required_scope` に渡しています。
- `docs/auth.md` の scope 表と `docs/client_integration.md` の MSAL scope を合わせます。

## payload を変える

| 順 | 更新先 | 内容 |
|---|---|---|
| 1 | `functions/sdui_api/models.py` | `ComponentPayload` / `ResolvedUiPayload` の `TypedDict` と `to_payload` |
| 2 | `functions/sdui_api/ui_resolver.py` の `etag_of` | `to_payload` 全体を hash するため、変動する値を入れていないか確認する |
| 3 | `functions/sdui_api/tests/test_function_app.py` / `test_ui_resolver.py` | 期待する本文の完全一致。ETag と 304 の既存テスト（`test_matching_etag_returns_empty_304_with_cache_headers`）も確認する |
| 4 | `scripts/dev_server.py` | `resolve_payload` は同じ `to_payload` と `etag_of` を使うため、独自の分岐を足した場合だけ追従する |
| 5 | `docs/client_integration.md` | レスポンス例、制約、ステータス表 |
| 6 | `docs/architecture.md` | UIスキーマや失敗表に影響する場合 |
| 7 | `sd-ui-app`（別リポジトリ） | 契約が変わる場合は Android 側へ通知する |

- `requiredEntitlements` はサーバー側で評価済みで、payload に含めません（`Component.to_payload`）。
- `props` の値はスカラーに限る前提です（アプリ側の制約）。object や配列を入れる前にアプリ側の対応を確認します。
- `type` の追加はアプリ更新まで描画されません。落ちはしないため、段階的に追加できます。
- 保存文書の形状は `seed/schemas/` と `scripts/seed_validation.py` が扱います。配信 payload には使いません。
- フィールドの削除・改名は古いアプリを壊し得ます。追加のみを基本とします。

## キャッシュ設定を surface ごとに変える

現在の `max-age` は `UI_CACHE_MAX_AGE_SECONDS` の1つの整数です。持たせ方で更新先が変わります。

| 持たせ方 | 更新先 |
|---|---|
| UI 定義の文書に持たせる | `ui-definition-implementation` の範囲（`seed/schemas/ui_definitions.schema.json`、`scripts/seed_validation.py`、`models.UiDefinition.from_document`、`seed/ui_definitions/*.json`）。API は `UiDefinition` から読む |
| 環境変数の対応表にする | `ROLE_ENTITLEMENTS` と同じ形式で `settings.py` に解析と検証を足し、`modules/sdui_api` の変数と `envs/*` を更新する |

- `settings.cache_max_age_seconds` を使う箇所は `_serve` の `not_modified` と `cache_headers` の2か所です。両方を同じ値に揃えます。
- `scripts/dev_server.py` は `DEFAULT_CACHE_MAX_AGE_SECONDS` を `_send_headers` で使います。
- `docs/architecture.md` と `docs/client_integration.md` は `max-age=60` を明記しているため、同じ変更で更新します。

## タイムアウトと再試行

`ui_repository.py` と `auth.py` の定数は `docs/architecture.md` の表と一致しています。

| 定数 | 値 |
|---|---|
| `JWKS_FETCH_TIMEOUT_SECONDS` | 3 |
| `JWKS_LIFESPAN_SECONDS` | 300 |
| `JWKS_REFRESH_COOLDOWN_SECONDS` | 30 |
| `JWKS_STALE_LIMIT_SECONDS` | 24 時間 |
| `COSMOS_OPERATION_TIMEOUT_SECONDS` | 4 |
| `COSMOS_CONNECT_TIMEOUT_SECONDS` | 2 |
| `COSMOS_READ_TIMEOUT_SECONDS` | 2 |
| `COSMOS_RETRY_TOTAL` | 1 |
| `COSMOS_RETRY_BACKOFF_MAX_SECONDS` | 1 |

- `retry_total=0` にすると SDK が 429 の再試行を既定の9回へ戻します。0 にしないでください。
- `enable_endpoint_discovery=False` は単一リージョン前提です。複数リージョン化するときに見直します。
- 値を変えたら `test_ui_repository.py` の `test_cosmos_client_is_bounded_by_timeouts_and_limited_retries` と `test_auth.py` の JWKS クライアント設定のテスト、`docs/architecture.md` の表と所要時間を同じ変更で更新します。

## テストの書き方

- HTTP 入口のテストは `function_app.get_ui_schema(_request(token))` を直接呼びます。`_request` は `azure.functions.HttpRequest` を組み立てます。Functions ホストは起動しません。
- 外部通信は `monkeypatch.setattr` で差し替えます。`entry` fixture は `load_settings`、`jwks_key_resolver`、`fetch_latest_definition`、`fetch_profile` を差し替え、`containers` fixture は `ui_repository._container` を差し替えて SDK の例外を再現します。
- JWT は `conftest.py` の `issue_token` fixture で生成します。署名鍵はテスト内で生成した RSA 鍵です。
- 失敗系は、ステータス、本文が `{"error": {"code": ...}}` のみであること、`ETag` と `Cache-Control` が無いこと、後続の外部呼び出しが行われないことを確認します。
- ログの検証は `caplog` で、`dependency=...` や `variable=...` が出ること、トークンと `oid` と環境変数の値が出ないことを確認します。
- SDK 例外の分類は `test_ui_repository.py` の `TRANSIENT_FAILURES` / `PERSISTENT_FAILURES` に追加します。
- `filterwarnings = ["error"]` のため、警告もテストの失敗になります。
- テストの構成と方針は [テスト](../../../../docs/testing.md) を参照します。

## 型

- `pyproject.toml` の `[tool.mypy]` は `strict = true`、`warn_unreachable`、`ignore-without-code` です。テストは対象外です。
- `cast()` で警告を消さず、`# type: ignore[<code>]` はコード付きで書きます。
- `Any` を許容するのは、保存文書、`props`、SDK の境界（JWT の署名鍵など）に限ります。
- 新しいモジュールもこのレベルで通します。引数なしの `python -m mypy` が CI と同じ実行です。

## 参考資料

- [docs/testing.md](../../../../docs/testing.md)
- [docs/coding_standards.md](../../../../docs/coding_standards.md)
- [docs/client_integration.md](../../../../docs/client_integration.md)
- [docs/commands.md](../../../../docs/commands.md)
