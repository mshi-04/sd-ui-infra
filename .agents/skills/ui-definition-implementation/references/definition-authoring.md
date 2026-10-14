# UI 定義の書き方と登録

`seed/` の文書の形、登録前検証の規則、登録手順です。方針は docs/ を正本とし、ここでは書くときに踏む箇所をまとめます。

## 文書の種類

| ディレクトリ | schema | 保存先 container の環境変数（既定はディレクトリ名） | id |
|---|---|---|---|
| `seed/ui_definitions/` | `seed/schemas/ui_definitions.schema.json` | `UI_DEFINITIONS_CONTAINER` | `{surface}:{version}` |
| `seed/account_profiles/` | `seed/schemas/account_profiles.schema.json` | `ACCOUNT_PROFILES_CONTAINER` | `userId` と同じ値 |

Partition key は `ui_definitions` が `/surface`、`account_profiles` が `/userId` です。

## ui_definitions のフィールド

| フィールド | 必須 | 内容 |
|---|---|---|
| `id` | 必須 | `{surface}:{version}` と一致させる。不一致は検証エラー |
| `surface` | 必須 | 画面識別子。空でない文字列 |
| `version` | 必須 | 空でない文字列。最新判定に使う |
| `revision` | 必須 | 空でない文字列。改訂情報。最新判定には使わない |
| `components` | 任意 | component の配列（再帰） |
| `variants` | 任意 | `audience`（必須）と `components` を持つ配列 |

component は `id` と `type` が必須で、`props`（object）、`requiredEntitlements`（文字列配列）、`children`（component 配列）は任意です。

## version と最新定義

| 規則 | 内容 |
|---|---|
| 比較 | 本番は `SELECT TOP 1 * FROM c WHERE c.surface = @surface ORDER BY c.version DESC`（`ui_repository.LATEST_DEFINITION_QUERY`）。モックは文字列比較で最大を選ぶ |
| 形式 | 現在のseedはゼロ埋めした `YYYY-MM-DD`。日付形式の強制や解析はしない |
| 注意 | 文字列順なので `"9"` は `"10"` より大きい。同じ surface では比較規則が揃った表現にする |
| 判定に使わないもの | ファイル名、読み込み順、`revision` |
| 重複 | 同じ surface と version は複数ファイルに置けない。内容や `revision` が同じでも、最新でない version でもエラー |
| 同じ id への登録 | upsert は同じ保存先を更新する |

重複の検出は `scripts/seed_validation.py` の `validate_seed`（`$.version: duplicates surface and version from <file>`）と、`scripts/dev_server.py` の `load_definitions`（`ValueError`）の両方にあります。

## 登録前検証

`validate_seed` が全ファイルを検証し、1 件でもエラーがあれば `seed_cosmos.py` は何も書き込みません。

| 種類 | 対象 | 内容 |
|---|---|---|
| JSON Schema | 全ディレクトリ | 必須項目と型。未知の `type`、`props` のキー、文書のフィールドは許容 |
| ID 整合 | `ui_definitions` | `$.id` が `{surface}:{version}` と一致 |
| ID 整合 | `account_profiles` | `$.id` が `userId` と一致 |
| 兄弟 ID 重複 | `ui_definitions` | `components`、各 `children`、各 variant の `components` の同じ配列内で `id` が重複しない |
| surface と version 重複 | `ui_definitions` | 上記のとおり |
| 警告 | `ui_definitions` | `props` の値が object または配列。登録は止めない |

- 同じ `id` が別の兄弟配列にあるのは正当です。variant の component が base と同じ `id` を持つ場合は上書きとして扱われます。
- profile のエラーは値を表示しません。profile の値をログや報告に写さないでください。

### test_seed_documents.py が見るもの

| テスト | 確認内容 |
|---|---|
| `test_every_seed_document_passes_validation` | 全 seed が検証を通る |
| `test_every_seed_directory_is_covered_by_validation` | `seed/` 直下のディレクトリが `RULES_BY_DIRECTORY` と `schemas` に一致 |
| `test_seed_variant_audiences_are_defined_roles_or_profile_audiences` | variant の `audience` が app role か profile の `audiences` にある |
| `test_seed_required_entitlements_are_granted_by_a_role_or_a_profile` | `requiredEntitlements` が role か profile のどちらかで付与される |

同じファイルには、`dashboard.json` の現在の内容に依存する期待値（匿名は `usage-summary` のみ、example profile は `billing-summary` が先頭、など）もあります。`dashboard.json` を変えるとき、または新 version を足すときは、このテストと `test_dev_server.py`、`test_seed_cosmos.py`、`docs/client_integration.md` の出し分け例も確認します。

- `test_seed_cosmos.py` は実 seed を複製し、文書数（`validated 2 documents`）と upsert 一覧を固定値で検証します。seed ファイルを足すと必ず直します。
- `test_dev_server.py::test_single_definition_keeps_existing_payload_and_etag` は最新定義の version、revision、ETag を固定値で検証します。より大きい version を足すと落ちます。
- `test_seed_documents.py` の `dashboard` fixture は `dashboard.json` をファイル名で読みます。新 version は別の fixture を足さないと、resolve テストが古い版のままになります。

## account profile

`seed/account_profiles/example.json` は固定のダミー識別子（全桁 0）を使います。実在の `oid`、メールアドレス、テナントIDは書きません。実登録で `id` と `userId` を対象ユーザーの `oid` に置き換える手順（[docs/getting_started.md](../../../../docs/getting_started.md) の「UI定義の投入」）は、ローカルだけの未コミットの編集です。コミットするファイルはダミー値のままにします。

| フィールド | 内容 |
|---|---|
| `id` / `userId` | 同じ値。本番の `userId` は Entra ID の `oid` |
| `entitlements` | 個別の追加付与。role の entitlement との和集合になる |
| `audiences` | variant の `audience` に一致させる追加の対象 |
| `preferences` | `theme`、`density`、`pinnedComponentIds`。省略時は `light` / `comfortable` / 空 |

モックサーバーでは `X-Dev-Oid` が `userId` と一致したときにこの profile が使われます。

## 登録手順

1. `.venv\Scripts\python scripts/seed_cosmos.py --dry-run` を実行する。endpoint も Azure の資格情報も要らず、Cosmos DB クライアントも作られない。
2. 出力の `would upsert <file> into <container>` が意図したファイルだけであることを確認する。
3. 実書き込みは `.venv\Scripts\python scripts/seed_cosmos.py --endpoint <cosmos-endpoint>`（`COSMOS_ENDPOINT` と `COSMOS_DATABASE` の環境変数でも指定できる）。ユーザーの承認を得てから実行する。Cosmos DB はキー認証が無効なため、実行者には data plane のロールと `az login` が要り、無いと検証後に 403 で失敗する。手順は [docs/getting_started.md](../../../../docs/getting_started.md) の「UI定義の投入」と [docs/commands.md](../../../../docs/commands.md) の Seed を参照する。
4. 事前検証は入力不備による途中登録を防ぐが、通信障害時に書き込み全体を原子的にするものではない。途中で失敗した場合の再実行は upsert なので同じ文書を更新する。

CI は `python scripts/seed_cosmos.py --dry-run` を `python` ジョブの最後に実行します（`.github/workflows/ci.yml` の `Validate seed documents`）。

## 新しい seed ディレクトリを足すとき

| 変更箇所 | 内容 |
|---|---|
| `seed/schemas/<ディレクトリ名>.schema.json` | `_schema_validator` がディレクトリ名から読む |
| `scripts/seed_validation.py` の `RULES_BY_DIRECTORY` | `DocumentRules(errors=..., warnings=...)` を登録 |
| `scripts/seed_cosmos.py` の `CONTAINER_BY_DIRECTORY` | 保存先 container を決める環境変数名 |
| `functions/sdui_api/tests/test_seed_validation.py` | 検証規則のテスト |

container 自体は Terraform の `modules/ui_store` で定義されています。配信側は `settings.py`（`UI_DEFINITIONS_CONTAINER` と `ACCOUNT_PROFILES_CONTAINER` だけを読む）、`ui_repository.py`、`models.py` に変更しないと、新しいディレクトリの文書は保存されても配信されません。配信は `api-implementation`、container と環境変数は `infra-implementation` を参照します。

## 参考資料

- [docs/architecture.md](../../../../docs/architecture.md)
- [docs/commands.md](../../../../docs/commands.md)
- [docs/testing.md](../../../../docs/testing.md)
