---
name: ui-definition-implementation
description: UI surface と UI 定義（seed/ui_definitions・seed/account_profiles・seed/schemas の surface / version / component / variant / requiredEntitlements）の設計・実装・修正に使う。登録前検証、最新定義の選択規則、component の上書き規則、モックサーバーでの確認、変更時に直すテストと文書を提供。
---

# UI Definition Implementation

## 実装手順

1. 変更が新規 surface、既存 surface の新 version、component・variant の変更、account profile の変更、schema・検証規則の変更のどれに当たるかを分ける。
2. `seed/ui_definitions/dashboard.json` と `seed/account_profiles/example.json` を開き、記述の粒度を確認する。surface は `ui/{surface}` ルートで受けるため、新しい surface に Terraform や API コードの変更は要らない。ただしアプリが要求する surface かを確認し、`docs/client_integration.md` の `surface` の説明（現在は `dashboard` のみ）を更新する。
3. 定義は `id` を `{surface}:{version}`、`version` を空でない文字列、`revision` を空でない文字列で書く。最新は文字列比較の最大値で決まり、ファイル名・読み込み順・`revision` は使われない。
4. 既存 surface の新 version は、`dashboard.json` を触らず別ファイル（例 `dashboard-2026-07-01.json`）にコピーし、`id` と、既存より文字列として大きい `version`（ゼロ埋めした `YYYY-MM-DD`）、新しい `revision` を設定してから components を編集する。同じ surface と version を別ファイルに置くと、最新でなくても登録前検証とモックの読込で拒否される。
5. component の `id` は同じ兄弟配列内で一意にする。variant の component が base と同じ `id` なら上書き、無ければ追加になる。入れ子の子を上書きするときは親の `id` を variant に繰り返し、`children` の下に置く。上書きでは `requiredEntitlements` を空にして要求を外せない。
6. variant の `audience` と `requiredEntitlements` は、`config/app_roles.json` の role 名と entitlement、または seed の profile の `audiences` と `entitlements` で定義済みの値だけを使う。audience は variant の選択だけで、entitlement は付与しない。新しい role や entitlement が要る場合は `app-role-implementation` に引き継ぐ。
7. `type` は Android クライアントが描画できる列挙（`Card` / `List` / `Chart` / `Button` / `Banner` / `Panel`）から選び、`props` の値はスカラーにする。新しい `type` や構造化 props はアプリ側（`sd-ui-app`）の対応が先になる。
8. seed ファイルを足すと `test_seed_cosmos.py` の文書数と upsert 一覧が変わるため期待値を直す。新 version を足すと `test_dev_server.py::test_single_definition_keeps_existing_payload_and_etag` も落ちる。`test_seed_documents.py` の `dashboard` fixture は `dashboard.json` をファイル名で読むため、新 version を読む fixture を足す。新 surface や entitlement を持つ component は同ファイルに resolve テスト（要求を満たさないと非表示、満たすと表示）を足す。
9. 新しい seed ディレクトリは `seed/schemas/<ディレクトリ名>.schema.json`、`scripts/seed_validation.py` の `RULES_BY_DIRECTORY`、`scripts/seed_cosmos.py` の `CONTAINER_BY_DIRECTORY` に登録し、配信には `api-implementation`、container と環境変数には `infra-implementation` を参照する。
10. resolver の規則や配信 payload の形を変える場合は `api-implementation` を参照し、`models.py` の `TypedDict` と `docs/client_integration.md` も更新する。`dashboard.json` の component を変えたら `docs/client_integration.md` の出し分け例の表と JSON 例も直す。
11. Cosmos DB への実書き込み（`--dry-run` なし）はユーザーの承認を得てから行う。まず `--dry-run` で確認する。誤った新 version は、古い文書を編集せず、より大きい version を登録して直す。文書の削除はユーザーの明示的な承認が要る。

## 検証手順

1. `.venv\Scripts\python scripts/seed_cosmos.py --dry-run`（CI と同じ。エラーが 1 件でもあれば何も書かず終了コード 1）
2. `.venv\Scripts\python -m pytest`（`test_seed_documents.py` が audience と entitlement の定義済みを確認する）
3. `.venv\Scripts\python -m ruff format --check functions scripts`、`.venv\Scripts\python -m ruff check functions scripts`、`.venv\Scripts\python -m mypy`
4. 別ターミナルかバックグラウンドで `.venv\Scripts\python scripts/dev_server.py --port 8080` を起動し、`X-Dev-Roles`（`SupportAgent` と `SupportAgent,BillingViewer` など）と `X-Dev-Oid` を変えて `Invoke-RestMethod` で `/api/ui/<surface>` の component tree を確認し、終わったらサーバーを止める（例は references/resolution-and-mock.md）。実書き込みを承認済みなら、dev の `/ui/<surface>` も確認する。

## 参考資料

- [references/definition-authoring.md](references/definition-authoring.md): 保存文書の形、version と id の規則、登録前検証、profile の書き方、登録手順
- [references/resolution-and-mock.md](references/resolution-and-mock.md): 解決フローと上書き規則、entitlement の経路、クライアントとの契約、モックサーバーの使い方
- [docs/architecture.md](../../../docs/architecture.md)
- [docs/client_integration.md](../../../docs/client_integration.md)
- [docs/testing.md](../../../docs/testing.md)
- [docs/commands.md](../../../docs/commands.md)
