# リクエスト処理の流れ

`GET /api/ui/{surface}` を処理する `functions/sdui_api` の骨格と、応答を決める規則です。
方針の正本は [アーキテクチャ](../../../../docs/architecture.md) と [認証・認可](../../../../docs/auth.md) です。

## 入口の骨格

`function_app.py` の `get_ui_schema` は例外の分類だけを担当し、本処理は `_serve` に置きます。

```python
@app.route(route="ui/{surface}", methods=["GET"])
def get_ui_schema(req: func.HttpRequest) -> func.HttpResponse:
    try:
        return _serve(req, surface)
    except SettingsError: ...              # 500 internal_error
    except DependencyUnavailableError: ... # 503 service_unavailable
    except DependencyError: ...            # 500 internal_error
    except Exception: ...                  # 500 internal_error（logger.exception）
```

`DependencyUnavailableError` は `DependencyError` のサブクラスなので、except の並びは
一時障害が先です。順序を入れ替えると 503 が 500 になります。

`_serve` の順序は次のとおりです。

| 手順 | 関数 | 失敗時 |
|---|---|---|
| 1. 設定読込 | `settings.load_settings()` | `SettingsError` → 500。外部呼び出しの前に返る |
| 2. Bearer 抽出 | `auth.extract_bearer_token` | `AuthError` → 401 |
| 3. トークン検証 | `auth.verify_token` | `AuthError` → 401、JWKS の一時障害は 503 |
| 4. 最新定義の取得 | `ui_repository.fetch_latest_definition` | 0件で 404、障害は 503 / 500 |
| 5. profile の取得 | `ui_repository.fetch_profile` | 不在は空 profile、障害は 503 / 500 |
| 6. 解決 | `ui_resolver.resolve` | 想定外の例外は 500 |
| 7. 応答 | `etag_of` → `not_modified` / `json_response` | なし |

認証を通る前に Cosmos DB へ触れないこと、定義が無いときに profile を読まないことを守ります。
`test_function_app.py` が `assert_not_called` で固定しています。

## 失敗の分類

| 状況 | 応答 | `code` | 発生元 |
|---|---|---|---|
| Bearer なし、署名・期限・`iss`・`aud` の不正、必須クレーム欠落、scope 不足 | 401 | `unauthorized` | `AuthError` |
| 定義の問い合わせが応答ページを返し、文書が0件 | 404 | `surface_not_found` | `fetch_latest_definition` が `None` |
| JWKS への接続失敗・timeout・HTTP エラー（`PyJWKClientConnectionError`） | 503 | `service_unavailable` | `auth.verify_token` |
| Cosmos DB の一時障害 | 503 | `service_unavailable` | `ui_repository._classified_failures` |
| Cosmos DB の恒常的な失敗、資格情報の取得失敗 | 500 | `internal_error` | `DependencyFailureError` |
| 環境変数の欠落・変換失敗 | 500 | `internal_error` | `SettingsError` |
| 保存データの不備（`from_document` の `KeyError` など）、resolver の不具合 | 500 | `internal_error` | 最後の `except Exception` |

`from_document` は `_classified_failures` の外で呼ばれるため、応答の解釈失敗は `DependencyFailureError` にならず最後の `except Exception` に届きます。`docs/architecture.md` は Cosmos DB の恒常的な失敗の行にこれを含めて書いているため、コードの挙動を優先して文書を確認してください。

- 一時障害の判定は `ui_repository._is_transient` です。`TRANSIENT_STATUS_CODES`（408 / 429 / 503 / 504）の `CosmosHttpResponseError`、
  または `TRANSIENT_ERROR_TYPES`（`CosmosClientTimeoutError`、`ServiceRequestError`、`ServiceResponseError`）だけが 503 になります。
  403 や `ClientAuthenticationError` は RBAC や managed identity の設定不備で起きるため、再試行を促さない 500 にします。
- 定義の問い合わせが応答ページなしで0件になった場合は、404 にせず `DependencyUnavailableError`（`query_without_response`）を投げます。
  `_QueryPageRecorder` が `response_hook` で応答ページの受信を記録しています。
- profile の `CosmosResourceNotFoundError` だけが空 profile になります。それ以外の失敗を空 profile に変換しません。
- 新しい外部呼び出しを足すときは、`_classified_failures` のような変換点を経由させ、入口の except を増やさないでください。

## ルートを足すとき

現在のルートは `ui/{surface}` の1本だけで、認証は `_serve` の中にインラインで書かれ、例外の分類は `get_ui_schema` にだけあります。

- 認証ブロックと except の並びをコピーしません。認証を `_authenticate` のような関数へ、except の並びを共通のデコレーターか関数へ切り出し、既存ルートと新ルートで共有します。切り出した後も、一時障害が先という except の順序を保ちます。
- 新しい関数にも 401 / 503 / 500 の分類とログ衛生を適用し、`test_function_app.py` に同じ観点のテスト（本文が `error.code` のみ、`ETag` なし、後続呼び出しなし）を足します。
- `scripts/dev_server.py` は `ROUTE_PREFIX = "/api/ui/"` の前方一致だけを受けるため、`/api/ui`（末尾 `surface` なし）などは 404 になります。新ルートはモックにも足し、`test_dev_server.py` にテストを足します。
- `docs/client_integration.md` の「エンドポイント」とステータス表、`docs/architecture.md` を更新し、`sd-ui-app` へ通知します。

## ui_repository に問い合わせを足すとき

- `_classified_failures(container_name)` の中で実行し、`_container` の取得も含めます。
- `fetch_latest_definition` の問い合わせは `partition_key=surface` の単一パーティションです。surface の一覧のような横断問い合わせ（`SELECT DISTINCT c.surface` など）は全パーティションを読み、`COSMOS_OPERATION_TIMEOUT_SECONDS`（4秒）に収まるかを確認します。
- 結果が0件になり得る問い合わせは `_QueryPageRecorder` を `response_hook` に渡し、応答ページが無い0件は `DependencyUnavailableError`（`query_without_response`）にします。azure-cosmos 4.9.0 は内部再試行でページ1に戻ると例外なしで0件を返します（`docs/architecture.md`）。
- 「呼び出し元が使える surface」を権限で絞る場合は、定義ごとに解決する必要があり、取得回数と4秒の予算に影響します。全 surface を返すか権限で絞るかは方針の判断なので、ユーザーに確認し、結果を `docs/architecture.md` に書きます。
- `test_ui_repository.py` の `TRANSIENT_FAILURES` / `PERSISTENT_FAILURES` に新しい関数の事例を足します。

## エラー本文とステータスの契約

- 本文は `{"error": {"code": "<code>"}}` のみです（`response.error_response`）。
- 503 に `Retry-After` は付けません。
- エラー応答に `ETag` と `Cache-Control` を付けません（`test_function_app.py` の `_assert_error` が確認します）。
- ステータスや `code` を足す場合は [クライアント連携](../../../../docs/client_integration.md) の表と `sd-ui-app` への影響を確認します。

## キャッシュヘッダー

`response.cache_headers` が 200 と 304 の両方で同じ3つのヘッダーを返します。

| ヘッダー | 値 |
|---|---|
| `ETag` | `ui_resolver.etag_of` が解決後 payload の SHA-256 先頭16文字を二重引用符で囲んだ文字列 |
| `Cache-Control` | `private, max-age=<UI_CACHE_MAX_AGE_SECONDS>`（既定 60） |
| `Vary` | `Authorization` |

- 304 は `If-None-Match` が ETag と文字列で完全一致した場合だけです。`W/` 付き、複数値、`*` は一致として扱わず 200 を返します。
- ETag は `revision` ではなく解決後 payload から作ります。権限や設定が変われば `revision` が同じでも ETag は変わります。
- 時刻やリクエスト ID など、リクエストごとに変わる値を `to_payload` に入れると ETag が毎回変わり、304 が返らずクライアントのキャッシュが働かなくなります。入れるなら定義の `revision` や保存データの更新時刻のような決定的な値にするか、`etag_of` の入力から除外します。同じ入力で2回呼んで ETag が一致し、2回目が 304 になるテストを足します。
- `Cache-Control` は 200 と 304 で同じ値でなければなりません。`max-age` を surface ごとに変える場合の呼び出し箇所は `change-checklist.md` を参照します。
- 応答がユーザーごとに異なるため、`Vary: Authorization` と `private` を外さないでください。
- `scripts/dev_server.py` は `max-age` に `DEFAULT_CACHE_MAX_AGE_SECONDS` を使い、`Vary` を付けません。差があることを前提に、契約の確認は `test_function_app.py` で行います。

## 認証

- 署名アルゴリズムは `SIGNING_ALGORITHMS = ["RS256"]`、必須クレームは `REQUIRED_CLAIMS`（`exp` / `nbf` / `iss` / `aud` / `oid`）です。
- scope は `scp` クレームを空白で分割して `settings.required_scope`（既定 `UiSchema.Read`）を含むか確認します。不足は `AuthError("insufficient_scope")` です。
- app role は `roles` クレームから `Principal.app_roles` に入り、`ui_resolver.granted_entitlements` が `ROLE_ENTITLEMENTS` で entitlement に展開します。
- 401 の理由は `AuthError.reason` としてログにのみ残し、応答では区別しません。
- JWKS は `jwks_key_resolver`（`lru_cache`）が `StaleIfErrorJWKClient` を返します。取得失敗時は最後の鍵集合を最長24時間（`JWKS_STALE_LIMIT_SECONDS`）使い続けます。

## ログ衛生

| 場面 | レベル | 残す内容 |
|---|---|---|
| 401 | info | `surface`、`reason` |
| 503 | warning | `surface`、`dependency`（`jwks`、`cosmos.<container>`）、`detail`（例外の型と status） |
| 恒常的な外部障害 | error | 同上 |
| 設定不備 | error | `surface`、`variable`、`problem`（`missing` / `invalid`） |
| 想定外の不具合 | error（traceback 付き） | `surface` |
| 成功 | info | `surface`、`masked_subject`、`revision`、component 数 |

- `ui_repository._describe` は例外の型と status しか返しません。Cosmos DB の例外メッセージには `oid` を含む文書パスが入り得るため、メッセージを `detail` に入れないでください。
- `settings._parsed` は `raise ... from None` で例外の連鎖を切ります。パーサーのメッセージが生の値を含むためです。
- `detail` や `problem` に値を足す変更は、`test_function_app.py` の `caplog` 検証（`SUBJECT not in caplog.text` など）が落ちる前提で見直します。

## 参考資料

- [docs/architecture.md](../../../../docs/architecture.md)
- [docs/auth.md](../../../../docs/auth.md)
- [docs/client_integration.md](../../../../docs/client_integration.md)
