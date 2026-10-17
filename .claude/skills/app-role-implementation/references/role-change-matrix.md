# role 変更の影響と引き渡し

変更の種類ごとに、Terraform の plan に現れる差分、確認すべき箇所、ユーザーへ伝える内容をまとめます。
plan の表現は `modules/identity` のコードから導いたもので、実際の差分は必ず plan で確認します。

## 変更の種類ごとの影響

| 変更 | `modules/identity` の差分 | `modules/sdui_api` の差分 | 注意 |
|---|---|---|---|
| role の追加 | `random_uuid.app_role[...]` の作成と `azuread_application.api` の in-place 更新 | `ROLE_ENTITLEMENTS` の更新 | 割り当てが済むまで誰のトークンにも載らない |
| entitlement の増減 | なし（`entitlements` は Entra のリソースに渡していない） | `ROLE_ENTITLEMENTS` の更新 | identity のリソース差分が出ないことを plan で確認する |
| `display_name` / `description` の変更 | `azuread_application.api` の in-place 更新 | なし | id は変わらず、割り当ては維持される想定 |
| role の削除 | `random_uuid.app_role[...]` の破棄と `azuread_application.api` の更新 | `ROLE_ENTITLEMENTS` の更新 | 削除を伴うため理由を説明する。seed と profile の参照を先に確認する |
| entitlement 名の変更 | なし | `ROLE_ENTITLEMENTS` の更新 | 追加、全参照の置換、旧名の削除として扱う。下の「entitlement 名の変更」を参照 |
| role のキー名の変更 | 旧キーの `random_uuid` の破棄と新キーの作成。id が変わる | `ROLE_ENTITLEMENTS` の更新 | 削除と追加として扱う |

`random_uuid.app_role` は role のキーで `for_each` するため、キーを変えると別のリソースになり id が採番し直されます。
Entra の割り当ては role の id に紐づきます。旧 id への割り当てが新しい role に引き継がれるとは扱わず、
operator が新しい role へ割り当て直す前提で、ユーザーに確認してから進めます。
Entra 側が旧 role の削除をどう処理するか（無効化の要否、既存割り当ての扱い）は、このリポジトリのコードからは確認できません。
plan と apply の結果を見て判断します。

## entitlement 名の変更

`ROLE_ENTITLEMENTS`（apply で変わる）と Cosmos DB の `ui_definitions`（seed の実行でのみ変わる）は別々に切り替わります。
一度に置換すると、反映の間に component が隠れる、または誤って出ます。次の順に進めます。

1. 新名を role に追加する（旧名は残す）。seed の `requiredEntitlements` と profile の entitlement、テストの定義を新名へ置換する。
2. apply と、承認を得た seed の実行（`--dry-run` 以外）で両方を反映する。
3. 旧名を role から外す。`git grep -n <旧名> -- functions seed docs config` で残りが無いことを確認する。

seed の編集は `ui-definition-implementation` に引き継ぎます。Cosmos DB の `account_profiles` に旧名が残っていないかは、テストでは分からないためユーザーに確認します。

## 変更後に壊れやすい参照

| 参照元 | 条件 | 検出するもの |
|---|---|---|
| `seed/ui_definitions/*.json` の `variants[].audience` | role 名にも profile の `audiences` にも無い | `test_seed_variant_audiences_are_defined_roles_or_profile_audiences` |
| `seed/ui_definitions/*.json` の `requiredEntitlements` | role も profile も付与しない | `test_seed_required_entitlements_are_granted_by_a_role_or_a_profile` |
| Cosmos DB の `account_profiles` の `audiences` / `entitlements` | seed 以外の実データ | テストでは検出されない |

実データの profile は Cosmos DB にあり、テストの対象外です。role 名を audience として profile に書いている場合は、
削除やリネームの前にユーザーへ確認します。profile の `audiences` と `entitlements` は role 割り当てと独立して効きます。
seed への変更は `ui-definition-implementation` を参照します。

## 追加するテスト

`docs/testing.md` は、role や entitlement の追加時に解決フローのテストを求めます。

| 目的 | 置き場所 | 参考にするテスト |
|---|---|---|
| role が entitlement を付与し component が現れる | `test_ui_resolver.py` | `test_app_role_grants_entitlement_without_a_profile` |
| 入れ子の component まで届く | `test_ui_resolver.py` | `test_ui_admin_role_reaches_nested_components` |
| profile の entitlement との和集合 | `test_ui_resolver.py` | `test_profile_entitlements_extend_role_entitlements` |
| 未登録の role が何も付与しない | `test_ui_resolver.py` | `test_unknown_role_grants_nothing` |
| seed が新しい role で解決できる | `test_seed_documents.py` | `test_configured_roles_open_the_seeded_components` |
| モックサーバーのヘッダー経由の出し分け | `test_dev_server.py` | `test_app_role_opens_components_for_an_unknown_account` |

トークンの `roles` を作るのは `conftest.py` の `issue_token(roles=[...])` です。既定は `["BillingViewer"]` です。
テストはすべて `functions/sdui_api/tests/` にあります。

## ユーザーへの割り当て（operator の作業）

app role の割り当ては Terraform の対象外です。割り当てに必要な Microsoft Graph の `AppRoleAssignment.ReadWrite.All` は
テナント全体の権限昇格に使えるため、Terraform には持たせていません。operator が Entra 管理センターまたは CLI で行います。
CLI の具体的なコマンドは docs にありません。

apply の完了後に、次をユーザーへ伝えます。

- 対象の環境（dev / prod）と、割り当てが必要な role 名
- 割り当て先のユーザーまたはグループは operator が決めること。この作業は Terraform でも Claude でも行わない
- prod は `app_role_assignment_required = true` のため、role を割り当てられていないユーザーは API にサインインできない
- dev は `false` のため、role が無くてもサインインできる。その場合は variant が適用されず、entitlement の要らない component だけが返る
- role は取得したトークンの `roles` クレームから読まれる。割り当て直後に既存のトークンへ反映されるかは確認が必要
- レスポンスは `Cache-Control: private, max-age=<ui_cache_max_age_seconds>`（既定 60 秒）でクライアントに保持され得る

動作確認で variant を試す場合は、`SupportAgent` を割り当てるか、profile の `audiences` に追加します
（[docs/getting_started.md](../../../../docs/getting_started.md) の動作確認）。

## 更新する文書

| 文書 | 更新する内容 |
|---|---|
| `docs/auth.md` | 「app role」の表（role と付与する entitlement） |
| `docs/client_integration.md` | 「出し分けの確認例」の表（`X-Dev-Roles` ごとの component） |
| `docs/getting_started.md` | 動作確認で使う role 名が変わる場合のみ |
| `docs/architecture.md` | 解決フローの仕様を変える場合のみ（`api-implementation`） |

## 承認が必要な操作

- `terraform apply`。`modules/identity` を含む plan は、差分を提示してから行う
- 置換・削除（role の削除とキー名の変更を含む）
- `develop` / `main` へのマージ。`.github/workflows/cd.yml`（実体は `reusable-deploy.yml`）が push で `terraform apply -auto-approve` を実行する
- Cosmos DB への実書き込み（`--dry-run` 以外の seed の実行。dev も対象）
- ユーザーへの role 割り当て（operator の作業）

PR の plan ジョブ（`.github/workflows/ci.yml` の `terraform-plan`）は dev の差分だけを出します。
prod の差分は、手元で `terraform -chdir=envs/prod plan -var-file=../../environments/prod.tfvars` を実行して確認します。

## 参考資料

- [docs/auth.md](../../../../docs/auth.md)
- [docs/infrastructure.md](../../../../docs/infrastructure.md)
- [docs/testing.md](../../../../docs/testing.md)
- [docs/getting_started.md](../../../../docs/getting_started.md)
