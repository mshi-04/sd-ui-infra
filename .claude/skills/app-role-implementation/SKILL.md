---
name: app-role-implementation
description: Entra ID の app role と、role が付与する entitlement の設計・実装・修正に使う。config/app_roles.json、modules/identity の app_role、ROLE_ENTITLEMENTS 設定、roles クレームから entitlement への変換を提供。
---

# App Role Implementation

## 実装手順

1. 変更の種類を分ける: role の追加 / entitlement の増減 / entitlement 名の変更 / `display_name`・`description` の変更 / role の削除 / role のキー名の変更。影響範囲は references/role-change-matrix.md で確認する。
2. `config/app_roles.json` だけを編集する。キーが role 名で、`roles` クレームの値と variant の `audience` になる。各 role に `display_name` / `description` / `entitlements` が必須（`modules/identity/variables.tf`）。命名は entitlement が `<領域>.<操作>`、role が PascalCase。
3. `envs/dev/main.tf` と `envs/prod/main.tf` は同じ JSON を読んで `modules/identity` と `modules/sdui_api`（`ROLE_ENTITLEMENTS`）へ渡す。通常は配線を変えない。
4. role のキー名は変えない。`random_uuid.app_role` の `for_each` キーのため id が変わる。削除と追加として扱い、旧 role の割り当てが引き継がれない前提でユーザーに確認する。
5. 新しい entitlement を導入するときは、全権限の `UiAdmin` にも付与するかユーザーに確認する。付与するなら `docs/auth.md` の表も更新する。
6. entitlement 名の変更は一度に置換しない。新名を併記して apply と seed 反映を済ませ、旧名を除く順にする。seed の実書き込みと Cosmos の profile の確認は承認を取る。seed の編集・登録前検証は `ui-definition-implementation` を参照する。
7. 変更後に `git grep -n <旧名> -- functions seed docs config` で残りを探して直す。手書きの複製は `test_ui_resolver.py`（`ROLE_ENTITLEMENTS`、inline の `definition`、profile を使うテスト）、`local.settings.json.example`、`test_function_app.py`（`BillingViewer` を変えるときのみ）。
8. role が付与する entitlement を要求する component を追加・変更するときは `ui-definition-implementation` に引き継ぎ、`test_seed_documents.py` の期待値と `docs/client_integration.md` の出し分け表も同じ変更で更新する。削除する role や entitlement を seed が使っていないことを先に確認する。
9. `test_ui_resolver.py` と `test_seed_documents.py` に解決フローのテストを追加する（`docs/testing.md`）。resolver や `auth.py` の変更は `api-implementation` を参照する。
10. `modules/identity` を含む plan の差分は apply の前にユーザーへ提示する。CD は push で `apply -auto-approve` を実行するため、マージ前に提示する（`infra-implementation`）。
11. ユーザーへの role 割り当ては operator が行い、Terraform では行わない。apply 後に環境と role 名を伝える。`docs/auth.md` の app role 表を更新する。

## 検証手順

1. `.venv\Scripts\python -m pytest`、`.venv\Scripts\python -m ruff format --check functions scripts`、`.venv\Scripts\python -m ruff check functions scripts`、`.venv\Scripts\python -m mypy`
2. `.venv\Scripts\python scripts/seed_cosmos.py --dry-run`（`--dry-run` のみ。`--endpoint` を付けた実行は Cosmos DB への書き込みで承認が必要）
3. `terraform fmt -check -recursive`
4. `terraform -chdir=envs/dev init -backend=false` と `terraform -chdir=envs/dev validate`（`envs/prod` も同様）。CI は `bootstrap` も検証するが、role の変更では触れない。
5. ローカルのみ（Azure 資格情報が必要）: `docs/getting_started.md` の手順で backend 付きの `terraform -chdir=envs/dev init` を行い、`environments/dev.tfvars` を example から用意して `plan -var-file=../../environments/dev.tfvars` を実行する。prod も同様。基盤が未構築なら先に構築が要る。JSON の欠落は plan で初めて検出される。
6. plan で `modules/identity` の変更と置換・削除の有無を確認し、ユーザーへ提示する。

## 参考資料

- [references/role-data-flow.md](references/role-data-flow.md): JSON から Terraform、app setting、トークン、resolver までの流れと各ファイルの役割
- [references/role-change-matrix.md](references/role-change-matrix.md): 変更の種類ごとの影響、割り当て作業の引き渡し、更新する文書
- [docs/auth.md](../../../docs/auth.md)
- [docs/architecture.md](../../../docs/architecture.md)
- [docs/infrastructure.md](../../../docs/infrastructure.md)
- [docs/testing.md](../../../docs/testing.md)
- [docs/client_integration.md](../../../docs/client_integration.md)
