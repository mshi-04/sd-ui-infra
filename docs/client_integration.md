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
| 200 | UIスキーマを返す。`ETag` と `Cache-Control: private, max-age=60` を伴う |
| 304 | `If-None-Match` が一致。ボディなし |
| 401 | トークンが無効、または `UiSchema.Read` scope が無い。理由は返さない |
| 404 | 未知の surface |

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

トークン検証は行わず、次のヘッダーで利用者を切り替えます。Azure へはデプロイされません。

| ヘッダー | 内容 |
|---|---|
| `X-Dev-Oid` | アカウント識別子。`seed/account_profiles/` の `userId` と一致すればその profile が適用される |
| `X-Dev-Roles` | app role をカンマ区切りで指定（例 `SupportAgent,UiAdmin`）。`config/app_roles.json` の entitlement が付与される |

Android エミュレーターからは `http://10.0.2.2:8080/api/` で到達します（`10.0.2.2` はホストの `127.0.0.1`）。
平文HTTPになるため、debug ビルドのみ cleartext を許可してください。実機の場合は `--host 0.0.0.0` で起動し、
ホストのLAN IPを指定します。

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

`sd-ui-app` の `develop`（`30870b7`）を読み取って確認した内容です。契約の大部分は実装済みです。

| 契約 | 実装 | 場所 |
|---|---|---|
| `GET ui/{surface}` | Retrofit interface | `data/remote/SdUiApi.kt` |
| `If-None-Match` と `ETag` | surface ごとにメモリキャッシュし、304 ならキャッシュを返す | `data/repository/DefaultUiSchemaRepository.kt` |
| 200 / 304 / 401 / 404 | sealed interface で分岐。その他は `HttpException` | `data/remote/UiSchemaRemoteDataSource.kt` |
| 未知の `type` をスキップ | `mapNotNull` で除去 | `data/mapper/UiSchemaMapper.kt` |
| 未知のキーを無視 | `Json { ignoreUnknownKeys = true }` | `data/di/NetworkModule.kt` |
| `X-Dev-Oid` / `X-Dev-Roles` | debug ビルドのみの Interceptor。Gradle プロパティから注入 | `debug/.../DevIdentityModule.kt` |
| 平文HTTP | `usesCleartextTraffic` は debug マニフェストのみ | `src/debug/AndroidManifest.xml` |

モックサーバーへ接続する場合の起動例です。

```bash
./gradlew installDebug -PAPI_BASE_URL=http://10.0.2.2:8080/api/ -PDEV_ROLES=BillingViewer
```

### 契約側が守るべき制約

アプリの実装から、サーバー側に次の制約が生まれています。

1. **`props` の値はスカラーに限る。** アプリは `JsonPrimitive` のみを `Map<String, String>` へ変換し、
   ネストした object と array は破棄します。構造を持たせたい場合はアプリ側の対応が先に必要です。
2. **`type` は列挙で固定。** 現在は `Card` / `List` / `Chart` / `Button` / `Banner` / `Panel` のみ描画されます。
   サーバーが新しい `type` を返しても、アプリを更新するまでその component は表示されません（落ちはしません）。
3. `theme` と `density` は省略可能として扱われ、既定値へフォールバックします。

### 未対応

- **MSAL が未導入です。** `Authorization` ヘッダーを送らないため、実APIへ向けると常に 401 になります。
  実APIへ切り替える前に、アプリ側でトークン取得とヘッダー付与が必要です。
- `X-Dev-*` ヘッダーは debug ビルド限定のため、release ビルドはモックサーバーに対しても匿名扱いになります。

## 実APIへの切り替え

1. `envs/dev` を apply し、output から `api_base_url`、`entra_client_app_client_id`、`entra_api_client_id` を取得
2. base URL を `https://sdui-api.example.invalid/api/` 系へ変更
3. `X-Dev-*` ヘッダーを外し、MSAL で取得した access token を `Authorization` に載せる

API 契約自体はモックと実APIで同一です。切り替えで変わるのは base URL と認証だけです。

Android はネイティブクライアントのため CORS は関係しません。
ブラウザから叩く予定ができた場合のみ、`allowed_origins` にオリジンを追加して apply します。
