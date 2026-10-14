# 解決フローとモックサーバー

定義が resolver でどう組み立てられるか、クライアントとの契約、ローカルでの確認方法です。実装は `functions/sdui_api/ui_resolver.py` にあります。

## 解決の順序

`resolve` は次の順に適用します。後段ほど優先度が高くなります。

| 段階 | 内容 | 実装 |
|---|---|---|
| 1 | base の `components` を起点にする | `UiDefinition.components` |
| 2 | `profile.audiences` と app role に一致する variant を、定義内の記述順に `_merge` する | `resolve` |
| 3 | entitlement を満たさない component を取り除く（子も再帰的に評価） | `_filter_by_entitlements` |
| 4 | `pinnedComponentIds` を先頭へ寄せる | `_apply_pins` |

variant は 3 より前に適用されるため、variant で追加した component にも `requiredEntitlements` が効きます。

## component の上書き規則

`_merge` は `id` が同じ component を上書き、無い `id` を末尾へ追加します。

| 項目 | 上書き時の挙動 |
|---|---|
| `type` | variant の値で置き換わる |
| `props` | キー単位の浅いマージ。同じキーは variant が勝ち、base のみのキーは残る |
| `requiredEntitlements` | variant 側が空でなければ置き換える。空なら base の要求を保つ（外せない） |
| `children` | 同じ規則で再帰的にマージ。新しい子は base の子の後ろに追加 |
| 追加された component | base の後ろに、variant の記述順で並ぶ |

- 入れ子の component の上書きは、同じ兄弟配列内の `id` でだけ対応づきます。variant のトップレベルに base の子（例 `invoice-list`）と同じ `id` を書いても上書きにならず、トップレベルへの追加になります。子を上書きするには、variant に親の `id` を繰り返し、その `children` に子を置きます。
- 複数の variant が同じ `id` を触る場合は、記述順で後の variant が勝ちます。
- 兄弟内で `id` が重複すると上書き対象が曖昧になるため、登録前検証が拒否します。
- 親が entitlement で除外されると、子の要求が満たされていても出力されません。
- `pinnedComponentIds` はトップレベルの `id` だけに効きます。除外済みや未知の `id` は無視され、重複は最初の出現位置で 1 回だけ並びます。

## entitlement と audience の出所

| 値 | 出所 |
|---|---|
| 付与される entitlement | `config/app_roles.json` の role が持つ `entitlements`（access token の `roles`）と `profile.entitlements` の和集合 |
| 一致する audience | `profile.audiences` と app role 名の和集合 |

- 未知の role は何も付与しません。
- 要求を持たない component は、role も profile も無い利用者にも返ります。
- `requiredEntitlements` はレスポンスに含まれません。クライアントに判断材料（role、entitlement）は返しません。
- 新しい entitlement を role に載せる、新しい role を足す変更は `config/app_roles.json` の編集と apply を伴います。`modules/identity` はテナント全体に影響するため、`app-role-implementation` に引き継ぎ、plan の差分をユーザーへ提示してから進めます。
- ユーザーへの role 割り当ては運用者が行い、Terraform では管理しません。

## revision と ETag

| 項目 | 内容 |
|---|---|
| `revision` | UI 定義の改訂情報。レスポンスにそのまま入る |
| ETag | 解決後 payload 全体の SHA-256 の先頭 16 桁（`etag_of`）を引用符で囲んだ値。`If-None-Match` と文字列で完全一致したときだけ 304 |

同じ `revision` でも、権限や設定で payload が変われば ETag は変わります。クライアントのキャッシュ判定には ETag を使います。`revision` は記録であり、最新の選択には使われません。payload に含まれるため、値を変えれば ETag も変わります。

## クライアントとの契約

詳細は [クライアント連携](../../../../docs/client_integration.md#レスポンス) を参照してください。

| 項目 | 制約 |
|---|---|
| `type` | 描画されるのは `Card` / `List` / `Chart` / `Button` / `Banner` / `Panel`。未知の `type` はその要素だけスキップされる（落ちない） |
| `props` | 値はスカラーに限る。object と配列はアプリが破棄する。登録前検証は警告を出すが止めない |
| `children` | レスポンスでは常に存在する（空配列を含む） |
| 未知のキー | クライアントは無視する |
| `theme` / `density` | 省略可能として扱われ、既定値へフォールバック |

新しい `type` の追加はアプリ側の対応が先です。`docs/client_integration.md` の記述（surface が `dashboard` のみという説明、`type` の列挙）を変える場合は、その文書も更新します。surface を足すときは `surface` の説明を、`dashboard` の component を変えるときは出し分けの確認例の表と JSON 例を直します。

## モックサーバー

Azure なしで seed と本番と同じ resolver の結果を返します。トークンは検証しません。

```powershell
.venv\Scripts\python scripts/dev_server.py --port 8080
```

| 項目 | 内容 |
|---|---|
| ルート | `GET /api/ui/<surface>`。未知の surface は 404 `surface_not_found` |
| `X-Dev-Oid` | 利用者識別子。省略時は `anonymous`。seed の `userId` と一致すればその profile を使う |
| `X-Dev-Roles` | app role のカンマ区切り。`config/app_roles.json` の entitlement が付与される |
| 読込 | リクエストごとに seed と `app_roles.json` を読み直す |
| 検証 | 登録前検証（schema と規則）は通らない。`--dry-run` を別に実行する |
| 重複 | 同じ surface と version があれば読込エラー（`ValueError`） |

確認例です。

```powershell
Invoke-RestMethod -Headers @{ "X-Dev-Roles" = "UiAdmin" } http://127.0.0.1:8080/api/ui/dashboard | ConvertTo-Json -Depth 10
```

Android エミュレーターからは `http://10.0.2.2:8080/api/` で到達します。アプリは `X-Dev-*` を送らないため、常に匿名として応答します。

## 参考資料

- [docs/architecture.md](../../../../docs/architecture.md)
- [docs/client_integration.md](../../../../docs/client_integration.md)
- [docs/auth.md](../../../../docs/auth.md)
