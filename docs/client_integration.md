# クライアント連携

この文書は、Android クライアントがUIスキーマAPIと通信するための契約と設定をまとめます。
アプリ側の実装は別リポジトリ（`sd-ui-app`）で行い、この文書を正本として参照します。

## エンドポイント

```
GET {base_url}/ui/{surface}
```

| 項目 | 内容 |
|---|---|
| `surface` | 画面識別子。現在は `dashboard` のみ |
| 認証 | `Authorization: Bearer <access token>` |
| 条件付き取得 | `If-None-Match: <etag>` |

| ステータス | 意味 |
|---|---|
| 200 | UIスキーマを返す。`ETag`、`Cache-Control: private, max-age=60`、`Vary: Authorization` を伴う |
| 304 | `If-None-Match` が一致。ボディなし |
| 401 | トークンが無効、または `UiSchema.Read` scope が無い。理由は返さない |
| 404 | 未知の surface |
| 500 | サーバー側の設定不備、保存データの不備、想定外の不具合。再試行しても回復しない前提で扱う |
| 503 | 署名鍵（JWKS）または Cosmos DB へ一時的に到達できない。時間をおいた再試行で回復し得る |

200 と 304 以外は、`{"error": {"code": "<code>"}}` の形の JSON を返します。本文はエラーコードのみで、失敗理由や例外の内容は含めません。

| ステータス | `code` |
|---|---|
| 401 | `unauthorized` |
| 404 | `surface_not_found` |
| 500 | `internal_error` |
| 503 | `service_unavailable` |

500 と 503 は、外部サービス障害時の応答を整理した際に追加した契約です。
外部サービスの障害を 401 や 404、空の profile として返すことはありません。
503 は `Retry-After` を付けません。再試行する場合はクライアント側で間隔を空け、回数を制限してください。

## レスポンス

```json
{
  "surface": "dashboard",
  "version": "2026-06-01",
  "revision": "a1b2c3",
  "theme": "dark",
  "density": "compact",
  "components": [
    {
      "id": "billing-summary",
      "type": "Card",
      "props": { "title": "Billing", "span": 6 },
      "children": [
        { "id": "invoice-list", "type": "List", "props": { "source": "invoices" }, "children": [] }
      ]
    }
  ]
}
```

- `components` は再帰構造で、`children` は常に存在します（空配列を含む）。
- `props` は component の `type` ごとに異なる自由形状です。未知のキーは無視してください。
- `type` が未知の component に遭遇した場合はクラッシュさせず、その要素だけスキップしてください。
  サーバー側で新しい `type` を追加しても、古いアプリが落ちないことを前提にしています。
- `requiredEntitlements` はサーバー側で評価済みで、レスポンスには含まれません。
- 同じユーザーでも権限や設定が変われば `revision` は同じまま `ETag` が変わります。
  キャッシュの一致判定には `ETag` を使ってください。
- 応答はトークンごとに異なるため、`Vary: Authorization` を付けています。`304` にも同じヘッダーが付きます。

## 認証（MSAL Android）

| 設定 | 値 |
|---|---|
| authority | `https://login.microsoftonline.com/<tenant_id>` |
| client_id | `envs/dev` の output `entra_client_app_client_id` |
| scope | `api://<entra_api_client_id>/UiSchema.Read` |
| redirect_uri | `msauth://<package>/<url-encoded signature hash>` |

実値は `envs/dev` の output から取得します。テナントIDを含め、この文書には実値を書きません。

```bash
terraform -chdir=envs/dev output
```

### redirect URI の求め方

署名証明書のハッシュから作ります。debug キーストアの場合:

```bash
keytool -exportcert -alias androiddebugkey -keystore ~/.android/debug.keystore -storepass android -keypass android | openssl sha1 -binary | openssl base64
```

出力を URL エンコード（`=` を `%3D` に置換）し、`msauth://<package>/<encoded>` の形にします。
この値を `environments/dev.tfvars` の `public_client_redirect_uris` に設定してから apply します。
debug と release で証明書が異なるため、両方の URI を登録してください。

## ローカル検証（apply 前）

Azure を使わずに、seed データと本番と同じ resolver でスキーマを返すサーバーを起動できます。

```bash
python scripts/dev_server.py --port 8080
```

同じsurfaceのseedが複数ある場合は、本番と同じく文字列比較で最大の `version` を選びます。ファイル名と `revision` は選択に使いません。同じsurface・versionを複数ファイルに置くと読込エラーになります。versionの表現と重複時の扱いは [最新定義の選択](architecture.md#最新定義の選択) を参照してください。

トークン検証は行わず、次のヘッダーで利用者を切り替えます。Azure へはデプロイされません。

| ヘッダー | 内容 |
|---|---|
| `X-Dev-Oid` | アカウント識別子。`seed/account_profiles/` の `userId` と一致すればその profile が適用される |
| `X-Dev-Roles` | app role をカンマ区切りで指定（例 `SupportAgent,UiAdmin`）。`config/app_roles.json` の entitlement が付与される |

Android エミュレーターからは `http://10.0.2.2:8080/api/` で到達します（`10.0.2.2` はホストの `127.0.0.1`）。
平文HTTPになるため、debug ビルドのみ cleartext を許可してください。実機の場合は `--host 0.0.0.0` で起動し、
ホストのLAN IPを指定します。
Android アプリはこれらのヘッダーを送らないため、アプリから接続した場合は常に匿名の利用者として応答します。

### 出し分けの確認例

| リクエスト | 返る component |
|---|---|
| ヘッダー無し | `usage-summary` |
| `X-Dev-Roles: BillingViewer` | `usage-summary`, `billing-summary`（子は `invoice-list` のみ） |
| `X-Dev-Roles: UiAdmin` | `usage-summary`, `billing-summary`（`refund-action` を含む）, `definition-inspector` |
| `X-Dev-Roles: SupportAgent` | `usage-summary`, `impersonation-banner` |
| `X-Dev-Oid: 00000000-0000-0000-0000-000000000000` | `billing-summary`（先頭に固定）, `usage-summary`, `impersonation-banner`。`theme` は `dark` |

同じ surface でも role と profile によって component tree が変わります。
実APIでは `X-Dev-Roles` の代わりに、access token の `roles` クレームが同じ役割を果たします。

## アプリ側の実装状況

`sd-ui-app` の `develop`（`b770c14`）を読み取って確認した内容です。契約の大部分は実装済みです。

| 契約 | 実装 | 場所 |
|---|---|---|
| `GET ui/{surface}` | Retrofit interface | `data/remote/SdUiApi.kt` |
| `If-None-Match` と `ETag` | surface ごとにメモリキャッシュし、304 ならキャッシュを返す | `data/repository/DefaultUiSchemaRepository.kt` |
| 200 / 304 / 401 / 404 | sealed interface で分岐。その他は `HttpException` | `data/remote/UiSchemaRemoteDataSource.kt` |
| 未知の `type` をスキップ | `mapNotNull` で除去 | `data/mapper/UiSchemaMapper.kt` |
| 未知のキーを無視 | `Json { ignoreUnknownKeys = true }` | `data/di/NetworkModule.kt` |
| `Authorization` | `MsalAuthClient` が取得した access token を `AuthorizationInterceptor` が付与。トークンが無ければヘッダー無しで送り、401 ならログイン画面へ戻る | `data/remote/AuthorizationInterceptor.kt` |
| 平文HTTP | `usesCleartextTraffic` は debug マニフェストのみ | `src/debug/AndroidManifest.xml` |

500 と 503 はこの確認より後に追加した契約です。上表の記録では、200 / 304 / 401 / 404 以外は `HttpException` として扱われます。
その後のアプリが 500 と 503 を区別するか、503 で再試行するかは確認していません。

base URL と scope は `gradle.properties` の `API_BASE_URL` と `API_SCOPE` で指定し、既定は dev の実APIです。
モックサーバーへ接続する場合の起動例です。

```bash
./gradlew installDebug -PAPI_BASE_URL=http://10.0.2.2:8080/api/
```

ダッシュボードへ進むにはサインインが必要です。`dev_server.py` はトークンを検証しないため、
アプリからは匿名として扱われ、`usage-summary` のみが返ります。

### 契約側が守るべき制約

アプリの実装から、サーバー側に次の制約が生まれています。

1. **`props` の値はスカラーに限る。** アプリは `JsonPrimitive` のみを `Map<String, String>` へ変換し、
   ネストした object と array は破棄します。構造を持たせたい場合はアプリ側の対応が先に必要です。
2. **`type` は列挙で固定。** 現在は `Card` / `List` / `Chart` / `Button` / `Banner` / `Panel` のみ描画されます。
   サーバーが新しい `type` を返しても、アプリを更新するまでその component は表示されません（落ちはしません）。
3. `theme` と `density` は省略可能として扱われ、既定値へフォールバックします。

### 未対応

`sd-ui-app` の `docs/server-contract.md`「未実装のもの」に挙がっている項目です。

- release ビルド用の redirect URI。アプリは debug キーストア由来の値だけを持ちます。
- `props` の object / 配列 / `null` 値の保持（上記の制約 1）
- `Button` などの component が持つ action の実行
- `ETag` と解決済みスキーマの永続化。キャッシュはメモリ上のみです。
- `Cache-Control` の尊重。`max-age` 内でも毎回サーバーへ条件付きで問い合わせます。

## 実APIへの切り替え

アプリは既定で dev の実APIを向き、MSAL で取得した access token を送ります。
実APIで動かすためにインフラ側で必要な手順は次のとおりです。

1. `envs/dev` を apply し、output から `api_base_url`、`entra_client_app_client_id`、`entra_api_client_id` を取得
2. アプリの `gradle.properties` の `API_BASE_URL` と `API_SCOPE`、MSAL 設定が output と一致しているか確認する

API 契約自体はモックと実APIで同一です。違いは base URL と、トークンを検証するかどうかだけです。

Android はネイティブクライアントのため CORS は関係しません。
ブラウザから叩く予定ができた場合のみ、`allowed_origins` にオリジンを追加して apply します。
