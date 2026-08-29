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

## Azure リソースへの認可

- Function App は system-assigned managed identity を持ちます。
- Cosmos DB へのアクセスは接続文字列ではなく、data plane role assignment で許可します。
- 付与するロールは組み込みの `Cosmos DB Built-in Data Reader` を基本とします。
- 書き込みが必要な運用操作は、CI/CD の service principal 側に限定します。

## ログ衛生

- access token、`upn`、`email`、氏名をログに出さないでください。
- `oid` はハッシュ化して出力します（`auth.mask_subject`）。
- 401 / 403 のログには surface と検証失敗の分類のみを残します。
