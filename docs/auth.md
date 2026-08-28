# 認証・認可

この文書は、Microsoft Entra ID を使った認証と、UI出し分けに使う認可情報を定義します。

## Entra ID アプリケーション

Terraform の `modules/identity` が2つのアプリケーションを管理します。

| アプリケーション | 用途 |
|---|---|
| API app (`sd-ui-api-<env>`) | access token の audience。scope と app role を公開する |
| Client app (`sd-ui-client-<env>`) | SPA。Authorization Code + PKCE で token を取得する |

### 公開する scope

| scope | 用途 |
|---|---|
| `UiSchema.Read` | UIスキーマの取得 |

### app role

| role | 用途 |
|---|---|
| `UiAdmin` | 全 surface の全 component を閲覧できる |
| `BillingViewer` | 請求系 component を閲覧できる |
| `SupportAgent` | サポート向け component を閲覧できる |

app role は audience の導出にのみ使い、entitlement の最終判定は account profile 側で行います。
role を増やすときは `modules/identity` と `docs/architecture.md` の解決フローを同時に更新します。

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
