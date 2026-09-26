# アーキテクチャ

この文書は、サーバー駆動UI（Server-Driven UI）の構成と、アカウントごとにUIが変わる仕組みを定義します。

## 全体像

```
Client (Web / Mobile)
  |  1. Entra ID でサインイン（Authorization Code + PKCE）
  |  2. access token を付けて GET /api/ui/{surface}
  v
Azure Functions (sdui_api)
  |  3. JWT 検証（署名 / iss / aud / scp / roles）
  |  4. Cosmos DB から base definition と account profile を取得
  |  5. resolver がマージして UI スキーマを生成
  v
Cosmos DB for NoSQL
  - ui_definitions   : surface ごとの base layout と variant
  - account_profiles : ユーザーごとの entitlement と preference
```

クライアントは画面構造を持たず、レスポンスの component tree を描画します。
出し分けの判断はすべてサーバー側で行い、クライアントには判断材料（role, entitlement）を返しません。

## Surface

`surface` は出し分けの単位となる画面識別子です（例: `dashboard`, `settings`）。
1つの surface は1つの base definition を持ち、その上に variant と account profile が重なります。

## UIスキーマ

```json
{
  "surface": "dashboard",
  "version": "2024-06-01",
  "revision": "a1b2c3",
  "components": [
    {
      "id": "billing-summary",
      "type": "Card",
      "props": { "title": "Billing" },
      "requiredEntitlements": ["billing.read"],
      "children": []
    }
  ]
}
```

- `revision` はUI定義の改訂情報です。キャッシュ判定には、利用者向けに解決したpayload全体から生成する ETag を使います。
- `requiredEntitlements` は解決時に評価され、レスポンスからは取り除かれます。

## 解決フロー

`ui_resolver` は次の順序で適用します。後段ほど優先度が高くなります。

1. base definition の component tree を起点にする
2. app role と account profile の `audiences` に一致する variant を適用する
3. entitlement で component を絞り込む
4. account profile の preference（theme, density, pinned components）を適用する

entitlement は2つの経路から集まり、和集合になります。

| 経路 | 出所 | 用途 |
|---|---|---|
| app role | Entra ID の role 割り当て → `config/app_roles.json` の対応表 | 役割単位の一括切り替え |
| account profile | Cosmos DB の `entitlements` | ユーザー個別の追加付与 |

role を割り当てるだけでUIが変わり、profile 文書は個別の上書きだけに使えます。
どちらも無いユーザーには、entitlement を要求しない component のみが返ります。

同じ `id` の component は上書き、存在しない `id` は追加として扱います。
評価は純粋関数として実装し、I/O は `ui_repository` に閉じ込めます。

## データモデル

### `ui_definitions`

| 項目 | 内容 |
|---|---|
| Partition key | `/surface` |
| id | `{surface}:{version}` |
| 主なフィールド | `components`, `variants`, `version`, `revision` |

### `account_profiles`

| 項目 | 内容 |
|---|---|
| Partition key | `/userId` |
| id | Entra ID の `oid` |
| 主なフィールド | `entitlements`, `preferences`, `audiences` |

`userId` は Entra ID の `oid` を使います。`email` や `upn` は識別子に使いません。

保存文書の形状は `seed/schemas/` の JSON Schema で定義し、`scripts/seed_cosmos.py` が登録前に検証します。
配信時の API は保存文書を検証しません。保存文書と配信 payload はフィールドが異なるため、この schema は配信 payload には使いません。

## キャッシュ

- レスポンスに `ETag` と `Cache-Control: private, max-age=60` を付与します。
- クライアントの `If-None-Match` が生成した ETag と文字列で完全一致した場合は `304` を返します。
- 現状は弱い ETag（`W/` 付き）、複数値のリスト、`*` を一致として扱いません。認証済みで対象surfaceが存在する場合は `200` を返します。
- UI定義の `revision` や解決結果が変わると ETag が変わります。同じ `revision` でも、権限や設定によってpayloadが変われば ETag は変わります。

## 外部サービス障害時の応答

`function_app.get_ui_schema()` は、設定読込から応答生成までの失敗を次のように分類します。
SDK 固有の例外は `ui_repository`（Cosmos DB）と `auth`（JWKS）で `dependency_errors` の例外へ変換し、HTTP 入口には SDK の型を持ち込みません。

| 失敗 | 例 | 応答 |
|---|---|---|
| 認証失敗 | トークン不正、期限切れ、scope 不足 | 401 `unauthorized`（従来どおり） |
| surface なし | 定義の問い合わせが応答ページを返し、文書が0件 | 404 `surface_not_found`（従来どおり） |
| profile なし | `read_item` が 404 | 空の profile で解決（従来どおり） |
| JWKS の一時障害 | 接続失敗、timeout、JWKS の HTTP エラー（`PyJWKClientConnectionError`） | 503 `service_unavailable` |
| Cosmos DB の一時障害 | 接続失敗、timeout（`ServiceRequestError` / `ServiceResponseError` / `CosmosClientTimeoutError`）、SDK の再試行後に残った 408 / 429 / 503 / 504 | 503 `service_unavailable` |
| Cosmos DB の恒常的な失敗 | 401 / 403 / 404（container なし）/ 500 などその他の status、資格情報の取得失敗（`ClientAuthenticationError`）、応答の解釈失敗 | 500 `internal_error` |
| 設定不備 | 必須環境変数の欠落、`UI_CACHE_MAX_AGE_SECONDS` の数値変換失敗、`ROLE_ENTITLEMENTS` の JSON・構造の不備 | 500 `internal_error` |
| 保存データの不備・想定外の不具合 | 必須フィールドの欠落、resolver の例外 | 500 `internal_error` |

- 503 は時間をおけば回復し得る失敗に限定します。403 や資格情報の失敗は RBAC や managed identity の設定不備で起きるため、再試行を促さない 500 にします。managed identity の一時的な取得失敗も 500 になりますが、SDK の例外から設定不備と区別できないためです。
- 定義の問い合わせや profile の読込が失敗した場合、404 や空の profile へは変換しません。
- azure-cosmos 4.9.0 のクエリは、SDK 内部の再試行（429 の再試行を使い切った後など）が最初のページ取得をやり直すと、例外を出さずに0件で終わります。定義の問い合わせは `response_hook` で応答ページを受け取ったかを記録し、ページなしの0件は 404 ではなく 503 にします。
- 設定の読込失敗は外部呼び出しの前に 500 を返します。応答とログに環境変数の値は含めません。

## タイムアウトと再試行

応答待ちを無制限にしないため、JWKS と Cosmos DB に明示的な上限を設定します。アプリ独自の再試行は行わず、SDK の再試行回数を絞ります。

| 対象 | 設定 | 値 | SDK の既定値 |
|---|---|---|---|
| JWKS | `PyJWKClient(timeout=...)`（接続・読み取りの各操作） | 3 秒 | 30 秒 |
| Cosmos DB | 操作ごとの `timeout`（クライアント生成時のアカウント取得、`query_items`、`read_item`） | 4 秒 | なし |
| Cosmos DB | `connection_timeout`（接続確立） | 2 秒 | 60 秒 |
| Cosmos DB | `RequestsTransport(read_timeout=...)`（応答の読み取り） | 2 秒 | 300 秒 |
| Cosmos DB | `retry_total`（接続の再試行と 429 の再試行回数） | 1 回 | 接続3回、429 は9回 |
| Cosmos DB | `retry_backoff_max`（再試行の待機上限、429 の累積待機上限） | 1 秒 | 429 は30秒 |
| Cosmos DB | `enable_endpoint_discovery` | 無効 | 有効 |

- 操作ごとの `timeout` は試行の合間に残り時間を確認する仕組みで、読み取り中の応答待ちは打ち切りません。接続の再試行も上限の外で重なるため、SDK の既定値のままでは、到達できない相手への `query_items(timeout=4)` が約13秒かかりました。このため接続と読み取りにも個別の上限を設けます。
- `retry_total` は 429 の再試行回数にも使われます。0 を渡すと SDK が 429 の回数を既定値の9回へ戻すため、1 にしています。
- アカウントは単一リージョンです。エンドポイント検出が有効だと、408 を受けた読み取りやクエリを待機なしで最大120回送り直すため無効にしています。複数リージョンにする場合は見直してください。
- Cosmos DB の定義クエリは、クライアントの container 情報が未取得の間、先に container の読込を行います。この読込には操作ごとの `timeout` が渡りませんが、接続・読み取りの上限と再試行回数で抑えられます。
- JWKS は、署名鍵の `kid` が見つからないと鍵集合を1回取り直すため、最大2回取得します。`timeout` は名前解決には効きません。

到達できない Cosmos DB を想定した計測では（ローカルの Python 3.14、azure-cosmos 4.9.0）、失敗が分類済みの例外になるまでの時間は次のとおりです。

| 条件 | 所要時間 |
|---|---|
| 接続拒否・応答のないアドレスでのクライアント生成 | 約4秒 |
| アカウント取得・container 読込の応答停止 | 約4秒 |
| 定義クエリ（POST）の応答停止 | 約2秒（応答待ちの POST は再試行しない） |
| profile 読込（GET）の応答停止 | 約4秒 |

1回の呼び出しは約4秒で打ち切られ、最初に失敗した呼び出しでリクエストは 503 か 500 になります。
すべての呼び出しが上限近くまで遅延しながら成功する最悪の場合でも、JWKS の2回（約6秒）と Cosmos DB の呼び出し（クライアント生成、container 読込、定義クエリ、profile 読込で各約4秒）の合計で、約22秒が上限の目安です。
クライアントと container 情報は再利用されるため、通常の失敗時は1回分の上限で応答します。

失敗は次の形でログに残します。Functions のホストが付与する呼び出し単位の相関情報と合わせて調査します。

| 失敗 | レベル | 記録する内容 |
|---|---|---|
| 503 | warning | `surface`、`dependency`（`jwks`、`cosmos.<container>`）、例外の型と HTTP status |
| Cosmos DB の恒常的な失敗 | error | 同上 |
| 設定不備 | error | `surface`、環境変数の名前、`missing` か `invalid` の区別 |
| 想定外の不具合 | error（traceback 付き） | `surface` と traceback |

ログ衛生の方針は [認証・認可](auth.md#ログ衛生) を参照してください。
