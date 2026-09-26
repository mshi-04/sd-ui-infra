# 認証・認可

この文書は、Microsoft Entra ID を使った認証と、UI出し分けに使う認可情報を定義します。

## Entra ID アプリケーション

Terraform の `modules/identity` が2つのアプリケーションを管理します。

| アプリケーション | 用途 |
|---|---|
| API app (`sd-ui-api-<env>`) | access token の audience。scope と app role を公開する |

`identifier_uris` は `azuread_application_identifier_uri` が管理します。
アプリケーション本体では `ignore_changes` を設定し、apply のたびに URI が消えるのを防ぎます。
| Client app (`sd-ui-client-<env>`) | Android の public client。Authorization Code + PKCE で token を取得する |

### 公開する scope

| scope | 用途 |
|---|---|
| `UiSchema.Read` | UIスキーマの取得 |

### app role

app role とその role が付与する entitlement は `config/app_roles.json` が正本です。
`envs/*` がこのファイルを読み、`modules/identity`（Entra への登録）と `modules/sdui_api`（`ROLE_ENTITLEMENTS` 設定）へ渡します。

| role | 付与する entitlement |
|---|---|
| `UiAdmin` | `billing.read`, `billing.write`, `support.read` |
| `BillingViewer` | `billing.read` |
| `SupportAgent` | `support.read` |

role を増やすときは `config/app_roles.json` を編集して apply します。Terraform と API の両方へ同時に反映されます。

ユーザーへの role 割り当ては `app_role_assignments` 変数（ユーザーの object id → role の一覧）で管理できます。
ポータルから割り当てた場合は Terraform の管理外になるため、どちらかに統一してください。

## トークン検証

`functions/sdui_api/auth.py` が次を検証します。

- 署名: `https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys` の JWKS
- アルゴリズム: `RS256`
- `iss`: `https://login.microsoftonline.com/{tenant_id}/v2.0`
- `aud`: API app の client id
- `exp` / `nbf`
- `scp` に `UiSchema.Read` を含むこと

検証に失敗した場合は理由を区別せず `401` を返します。失敗理由はログにのみ残します。

JWKS を取得できない場合（接続失敗、timeout、JWKS の HTTP エラー）はトークンの正否を判定できないため、`401` ではなく `503` を返し、Cosmos DB へは進みません。
取得の timeout は3秒です（PyJWT の既定値は30秒）。鍵は `kid` ごとにキャッシュされるため、JWKS の障害が影響するのは未取得の鍵を使うトークンです。
上限値の根拠と応答の分類は [アーキテクチャ](architecture.md#外部サービス障害時の応答) を参照してください。

## Azure リソースへの認可

- Function App は system-assigned managed identity を持ちます。
- Cosmos DB へのアクセスは接続文字列ではなく、data plane role assignment で許可します。
- 付与するロールは組み込みの `Cosmos DB Built-in Data Reader` を基本とします。
- 書き込みが必要な運用操作は、CI/CD の service principal 側に限定します。

## ログ衛生

- access token、`upn`、`email`、氏名をログに出さないでください。
- `oid` はハッシュ化して出力します（`auth.mask_subject`）。
- 401 / 403 のログには surface と検証失敗の分類のみを残します。
- 外部サービス障害（500 / 503）のログには、surface、依存先（`jwks`、`cosmos.<container>`）、例外の型と HTTP status のみを残します。Cosmos DB の例外メッセージには文書のパス（`oid` を含む）が入り得るため、メッセージと traceback は出しません。
- 設定不備のログには環境変数の名前と `missing` / `invalid` の区別のみを残し、値は出しません。変換エラーのメッセージは値を含むため、例外の連鎖も切ります。
- 想定外の不具合は、原因調査のため `logger.exception` で traceback を残します。トークンの検証失敗と外部サービスの例外はこの経路へ届く前に分類済みで、traceback にはローカル変数が含まれないため、トークンや `oid` が出ない前提です。例外メッセージに値を含める処理を追加する場合は、この前提を見直してください。
