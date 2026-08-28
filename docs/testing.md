# テスト

この文書は、`functions/sdui_api` のテスト構成と方針を定義します。

## 構成

| パス | 役割 |
|---|---|
| `functions/sdui_api/tests/conftest.py` | 共通の fixture（署名鍵、トークン生成、UI定義） |
| `functions/sdui_api/tests/test_auth.py` | JWT 検証の分岐 |
| `functions/sdui_api/tests/test_ui_resolver.py` | 解決フローの優先順位 |
| `functions/sdui_api/tests/test_seed_documents.py` | `seed/` の初期データが解決できること |

実行は `pytest` です。`pyproject.toml` の `pythonpath` により `functions/sdui_api` を import できます。

## 方針

- Cosmos DB と JWKS エンドポイントへの実アクセスはテストに含めません。
- JWT はテスト内で生成した RSA 鍵で署名し、JWKS はローカルの鍵集合に差し替えます。
- resolver は純粋関数として、I/O を介さずに検証します。
- 認証の失敗系は、期限切れ、audience 不一致、issuer 不一致、scope 不足を最低限カバーします。
- UI出し分けは、entitlement 不足による除外と、variant の上書き順序を必ず検証します。

## 追加時の基準

- API契約（レスポンス形状、ステータスコード）を変える変更にはテストを伴わせます。
- app role や entitlement を追加した場合、解決フローのテストを追加します。
- インフラのみの変更（Terraform）にはテストを求めず、`plan` の結果を検証とします。
