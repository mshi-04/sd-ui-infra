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
