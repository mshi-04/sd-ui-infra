# テスト

この文書は、`functions/sdui_api` のテスト構成と方針を定義します。

## 構成

| パス | 役割 |
|---|---|
| `functions/sdui_api/tests/conftest.py` | 共通の fixture（署名鍵、トークン生成、設定用の環境変数、クエリ応答の模擬） |
| `functions/sdui_api/tests/test_auth.py` | JWT 検証の分岐、JWKS 取得失敗の分類、JWKS クライアントの timeout |
| `functions/sdui_api/tests/test_function_app.py` | 本番 HTTP 入口の認証・解決・条件付き取得・エラー応答（401 / 404 / 500 / 503）の契約 |
| `functions/sdui_api/tests/test_ui_repository.py` | Cosmos DB の profile 欠落を空 profile に変換する境界、SDK 例外の一時障害・恒常的失敗への分類、クライアントの timeout・再試行設定 |
| `functions/sdui_api/tests/test_ui_resolver.py` | 解決フローの優先順位 |
| `functions/sdui_api/tests/test_seed_documents.py` | `seed/` の全ファイルが登録前検証に通り、初期データが解決できること。variant の audience と requiredEntitlements が `config/app_roles.json` の role か seed の profile で定義されていること |
| `functions/sdui_api/tests/test_seed_validation.py` | 保存文書の JSON Schema と、ID 整合・兄弟間の ID 重複の検証規則 |
| `functions/sdui_api/tests/test_seed_cosmos.py` | 登録スクリプトの dry-run と、不正データがあるときに書き込まないこと |
| `functions/sdui_api/tests/test_dev_server.py` | モックサーバーの解決結果、ヘッダー解釈、surfaceごとの最新version選択と定義重複の拒否 |
| `functions/sdui_api/tests/test_constants.py` | `ROLE_ENTITLEMENTS` の解釈、設定読込の失敗（欠落・変換失敗）で値を出さないこと |

実行は `pytest` です。`pyproject.toml` の `pythonpath` により `functions/sdui_api` を import できます。

`functions/sdui_api/tests/` は現在 mypy の対象外です。型チェックの対象範囲と方針は [コーディング規約](coding_standards.md#type-checking) を参照してください。

## 方針

- Cosmos DB と JWKS エンドポイントへの実アクセスはテストに含めません。
- JWT はテスト内で生成した RSA 鍵で署名し、JWKS はローカルの鍵集合に差し替えます。
- resolver は純粋関数として、I/O を介さずに検証します。
- HTTP 入口は `azure.functions.HttpRequest` で呼び出し、Cosmos DB と JWKS の外部通信を差し替えて、ステータス・本文・キャッシュヘッダーを検証します。認証の暗号処理は既存の JWT fixture を再利用します。
- `test_dev_server.py` はモックサーバーの解決処理とヘッダー値解釈を検証し、モックのHTTPハンドラー自体は呼び出しません。`test_function_app.py` は本番の入口関数を直接呼び、その応答オブジェクトを検証します。Functionsホストを起動するHTTP通信テストではありません。
- `If-None-Match` は現在 ETag との文字列完全一致のみを判定します。弱い ETag・複数値・`*` の扱いは入口テストで現状の制約として固定します。
- 登録前検証は `tmp_path` に作った seed で検証し、Cosmos DB クライアントと資格情報は記録用の偽物に差し替えます。dry-run ではどちらも生成されないことを確認します。
- 定義選択は、複数version、ファイル名とversionの逆順、複数surface、文字列としてのversion比較、revisionに依存しないことを検証します。同一surface・versionの重複は、最新以外のversionも含めてモックと登録前検証で拒否します。本番側は最新1件を要求するクエリ、parameter、partition keyを確認し、偽物のDBに独自の並べ替えを実装してCosmos DBの動作を検証したとは扱いません。
- 外部サービスの障害は、SDK の例外を差し替えた container や鍵解決から発生させます。一時障害が 503、恒常的な失敗が 500 になり、404 や空の profile にならないこと、本文がエラーコードのみであること、ログにトークンと `oid` が出ないことを確認します。
- 設定読込の失敗は環境変数を書き換えて再現します。`load_settings()` のキャッシュはケースごとにクリアし（`settings_environment` fixture）、JWKS と Cosmos DB の呼び出しへ進まないことを確認します。
- 認証の失敗系は、期限切れ、audience 不一致、issuer 不一致、scope 不足を最低限カバーします。
- UI出し分けは、entitlement 不足による除外と、variant の上書き順序を必ず検証します。
- 警告はエラーとして扱います（`filterwarnings = ["error"]`）。無視が必要な場合は対象を絞り、理由を添えます。

## 追加時の基準

- API契約（レスポンス形状、ステータスコード）を変える変更にはテストを伴わせます。
- app role や entitlement を追加した場合、解決フローのテストを追加します。
- `seed/` にファイルを追加するだけなら、テストの追加は不要です。`test_seed_documents.py` が全ファイルを検証します。新しいディレクトリを追加する場合は、`scripts/seed_validation.py` に検証規則と schema を追加します。
- インフラのみの変更（Terraform）にはテストを求めず、`plan` の結果を検証とします。
