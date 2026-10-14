# app role のデータフロー

`config/app_roles.json` から、Entra ID のトークンに載る role と、API が解決する entitlement までの流れです。
role の定義は1か所に置き、Terraform・API・モックサーバー・テストが同じファイルから読みます。

## 正本

[config/app_roles.json](../../../../config/app_roles.json) が正本です。キーが role 名です。

| フィールド | 用途 |
|---|---|
| キー（`UiAdmin` など） | Entra の app role の `value`。トークンの `roles` クレームの値。variant の `audience` との照合にも使われる |
| `display_name` | Entra の app role の表示名 |
| `description` | Entra の app role の説明 |
| `entitlements` | role が付与する entitlement の文字列配列 |

現在の定義は次のとおりです。

| role | entitlement |
|---|---|
| `UiAdmin` | `billing.read`, `billing.write`, `support.read` |
| `BillingViewer` | `billing.read` |
| `SupportAgent` | `support.read` |

命名は、entitlement が `<領域>.<操作>`（小文字、ドット区切り）、role が PascalCase です。
どちらも文書化された規則ではなく、現在の定義に共通する形です。新しい名前も合わせます。

## 流れ

| 段階 | ファイル | 内容 |
|---|---|---|
| 1. 読込 | `envs/dev/main.tf`、`envs/prod/main.tf` | `local.app_roles = jsondecode(file("${path.module}/../../config/app_roles.json"))` |
| 2. Entra へ登録 | `modules/identity/main.tf` | `random_uuid.app_role`（`for_each = var.app_roles`）で id を採番し、`azuread_application.api` の `dynamic "app_role"` が `value = app_role.key`、`allowed_member_types = ["User"]` で登録する |
| 3. API へ渡す | `modules/identity/outputs.tf` | `role_entitlements = { for name, role in var.app_roles : name => role.entitlements }` |
| 4. app setting | `modules/sdui_api/main.tf` | `ROLE_ENTITLEMENTS = jsonencode(var.role_entitlements)`。変数の型は `map(list(string))` |
| 5. 設定の解釈 | `functions/sdui_api/settings.py` | `parse_role_entitlements` が `Mapping[str, frozenset[str]]` に変換する。未設定時の既定値は `"{}"` |
| 6. トークン検証 | `functions/sdui_api/auth.py` | `verify_token` が `claims.get("roles", [])` を `Principal.app_roles` に入れる |
| 7. 解決 | `functions/sdui_api/ui_resolver.py` | `resolve` と `granted_entitlements` が role を audience と entitlement に展開する |

`modules/identity` の `app_roles` 変数は `display_name`、`description`、`entitlements` を持つ object の map です。
JSON にこの3つが欠けた role があると型エラーになります。値は `jsondecode(file(...))` で得るため `terraform validate` では評価されず、plan で初めて検出されます。

## 解決フローでの扱い

`ui_resolver.resolve` は role を2通りに使います。

| 用途 | 実装 | 補足 |
|---|---|---|
| variant の選択 | `profile.audiences` と `principal.app_roles` の和集合を audience とする | role のキーそのものが audience になる。対応表に無い role でも variant には一致する |
| entitlement の付与 | `granted_entitlements` | 各 role の `role_entitlements.get(role, ())` と `profile.entitlements` の和集合 |

- 対応表に無い role は entitlement を付与しません（`test_unknown_role_grants_nothing`）。
- component は `required_entitlements <= entitlements`（部分集合）のときだけ残ります。
- 適用順は variant、entitlement の絞り込み、pin です。
- variant の `requiredEntitlements` は、空でなければ base の要求を置き換えます。

role と entitlement はレスポンスに含まれません。クライアントが受け取るのは解決済みの component tree だけです。
ETag は解決後の payload から作るため、role の変更で結果が変わると ETag も変わります。

## 設定の不備

`ROLE_ENTITLEMENTS` が JSON として不正、または role が文字列配列に対応していない場合、`load_settings` は
`SettingsError("ROLE_ENTITLEMENTS", "invalid")` を送出し、API は `500 internal_error` を返します。
ログには変数名と `invalid` のみを残し、値は出しません。Terraform の型が先に弾くため、通常は起きません。
手で app setting を書き換えたときの失敗モードです。

## 手書きで複製している箇所

JSON を読まずに role の対応表を持つ箇所です。role や entitlement を変えたら同期します。

| ファイル | 内容 |
|---|---|
| `functions/sdui_api/tests/test_ui_resolver.py` | `ROLE_ENTITLEMENTS` 定数（3 role）、inline の `definition`（`requiredEntitlements` に `billing.write`）、profile に entitlement を持たせるテスト |
| `functions/sdui_api/local.settings.json.example` | `ROLE_ENTITLEMENTS` の JSON 文字列 |

`test_function_app.py` の `settings` fixture（`BillingViewer` のみ）は独立した最小の fixture です。`BillingViewer` の定義を変えるときだけ直します。

JSON を直接読むのは `scripts/dev_server.py`（`load_role_entitlements`）と `test_seed_documents.py`（`_role_entitlements`）です。
どちらも `role["entitlements"]` を参照するため、JSON の形を変える場合はこの2か所も直します。

## モックサーバー

`scripts/dev_server.py` は `X-Dev-Roles` ヘッダー（カンマ区切り）を `Principal.app_roles` に変換し、
本番と同じ `resolve` に渡します。トークン検証はしません。role を足したら、このヘッダーで出し分けを確認できます。

## 参考資料

- [docs/auth.md](../../../../docs/auth.md)
- [docs/architecture.md](../../../../docs/architecture.md)
- [docs/client_integration.md](../../../../docs/client_integration.md)
