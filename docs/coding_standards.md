# コーディング規約

この文書は、Terraform、Python、ドキュメントの共通規約を定義します。

## Common

- コード、変数名、関数名、コメントは英語で書いてください。
- ドキュメントは日本語で構いません。
- 変更は既存の構成、命名、ヘルパー、テスト配置に合わせてください。
- シークレット、テナントID、サブスクリプションID、個人情報をコードや例に含めないでください。
- 無関係な整形やリファクタリングを混ぜないでください。
- 字面から読み取れる説明をコメントに書かないでください。名前と構造で意図を表します。

## Terraform

### Structure

- ルートモジュールは `envs/<env>/` に置きます。
- 再利用可能なリソースは `modules/<name>/` に置きます。
- 標準構成は `main.tf`、`variables.tf`、`outputs.tf` です。
- モジュール内で `provider` ブロックを定義しないでください。
- モジュール内に環境分岐を持ち込まないでください。差異は `envs/*` から変数として渡します。

### Variables And Outputs

- 変数には `description` と `type` を付けます。
- 不正値を防げる場合は `validation` を使います。
- 他モジュールや運用で必要な値は `outputs.tf` に出します。
- 機密値を output する場合は `sensitive = true` を設定します。

### Authorization

- Azure リソース間の認可は接続文字列ではなく managed identity と RBAC を使います。
- `azurerm_role_assignment` は組み込みロールを優先し、`Owner` と `Contributor` をアプリケーションに割り当てないでください。例外は、環境ごとのデプロイ用 ID が自環境のリソースグループに持つ `Contributor` です（[インフラストラクチャ](infrastructure.md) を参照）。
- スコープはサブスクリプションではなく、対象リソースまで絞ります。

### Style

- `terraform fmt -recursive` を実行してください。
- タグは `bootstrap/` のリソースグループへ付与し、配下リソースは Azure Policy の
  `Inherit a tag from the resource group` で継承させます。モジュール内で個別にタグを持たせないでください。
- 名前変更やモジュール移動では、resource replacement と state move の必要性を確認します。

## Python Functions

### Style

- Python 3.14 を前提にします。
- 関数の引数と戻り値には型ヒントを付けます。
- `ruff format` と `ruff check` に従います。
- ビジネスロジックをトリガー関数に詰め込まず、責務ごとに分けます。

### Type Checking

- 型チェックは `mypy` で行い、ローカルと CI は同じ `python -m mypy` を引数なしで実行します。対象範囲と検査レベルは `pyproject.toml` の `[tool.mypy]` だけで決め、コマンド引数で変えません。
- 対象は `functions/sdui_api` と `scripts` です。`functions/sdui_api/tests/` は `exclude` で対象外にしています。import は `mypy_path` の2つのルートから、実行時と同じトップレベル名（`from models import ...`）で解決します。
- 対象外のファイルでも、対象モジュールから import されると解析され、エラーも報告されます。対象範囲を変えたときは `python -m mypy --verbose` の `Found source` 行で実際に検査したファイルを確認し、意図的な型不整合が検出されることを一度確かめます。
- 検査レベルは `strict = true` に `warn_unreachable` と `ignore-without-code` を加えたものです。新しいモジュールもこのレベルで通します。
- テストを対象へ加えるときは `exclude` を外し、fixture とテスト関数に型注釈を付けてから有効にします。一度に通せない場合に限り、`[[tool.mypy.overrides]]` で該当モジュールだけを緩め、理由をその設定か変更の説明に残します。
- 配信 payload の形状は `models.py` の `TypedDict`（`ComponentPayload`、`ResolvedUiPayload`）で表します。payload のフィールドを変えるときは `TypedDict` も合わせて変更します。
- 保存文書、`props` のような任意形状の JSON、SDK の境界（JWT の署名鍵など）に限り `Any` を許容します。型チェックは実際に受け取る JSON の妥当性を保証しません。保存文書の形状は登録前検証（`scripts/seed_validation.py`）が扱います。
- 警告を消すための `cast()` や広域な無視設定は使いません。`# type: ignore` はエラーコード付き（`# type: ignore[<code>]`）で書き、理由が字面から読み取れない場合は短く添えます。不要になった ignore は `warn_unused_ignores`（`strict` に含まれる）で検出されます。
- 依存ライブラリのうち `azure-functions`、`azure-cosmos`、`azure-identity`、`azure-core`、`PyJWT` は型情報（`py.typed`）を同梱しています。`jsonschema` は同梱しないため、typeshed の `types-jsonschema` を開発依存に固定しています。
- 型情報のないライブラリを追加するときは、公式のスタブパッケージがあれば開発依存に固定します。無い場合は全体の `ignore_missing_imports` を使わず、`[[tool.mypy.overrides]]` でそのモジュールに限って `ignore_missing_imports = true` を設定します。

### Azure Clients

- Cosmos DB クライアントはモジュールスコープで生成し、実行間で再利用します。
- 認証は `DefaultAzureCredential` を使い、接続文字列を扱いません。
- 外部サービス呼び出しはタイムアウト、エラー処理、ログの粒度を意識します。

### API Behavior

- API系の関数は `auth.py` パターンで Entra ID JWT を検証します。
- レスポンスは `response.py` パターンに合わせます。
- エラー時もレスポンス形式を崩さないでください。
- 既存のAPI契約を変える場合は、テストとドキュメントを更新します。

### Logging

- PII、生トークン、認証情報をログに出さないでください。
- `oid` などの識別子は `auth.mask_subject` でマスクします。
- ログは原因調査に必要な最小限の文脈に留めます。

## Git

- コミットメッセージは日本語で書きます。
- 件名は `<type>: <日本語の要約>` の形にします。`type` は `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `ci` を使います。
- 件名は現在形の体言止めか動詞で終え、何を変えたかが分かる粒度にします。
- 無関係な変更を1つのコミットへ混ぜないでください。
- ブランチ名は英語の kebab-case です（`feature/<内容>`）。

## Documentation

- 手順は実行可能なコマンドと前提条件を分けて書きます。
- 禁止事項、承認が必要な操作、検証ステータスは他文書と矛盾させないでください。
- エージェント向け入口は短くし、詳細は領域別文書へ分けます。
