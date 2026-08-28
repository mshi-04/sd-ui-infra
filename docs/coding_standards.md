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
- `azurerm_role_assignment` は組み込みロールを優先し、`Owner` と `Contributor` をアプリケーションに割り当てないでください。
- スコープはサブスクリプションではなく、対象リソースまで絞ります。

### Style

- `terraform fmt -recursive` を実行してください。
- タグは `bootstrap/` のリソースグループへ付与し、配下リソースは Azure Policy の
  `Inherit a tag from the resource group` で継承させます。モジュール内で個別にタグを持たせないでください。
- 名前変更やモジュール移動では、resource replacement と state move の必要性を確認します。

## Python Functions

### Style

- Python 3.12 を前提にします。
- 関数の引数と戻り値には型ヒントを付けます。
- `ruff format` と `ruff check` に従います。
- ビジネスロジックをトリガー関数に詰め込まず、責務ごとに分けます。

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

## Documentation

- 手順は実行可能なコマンドと前提条件を分けて書きます。
- 禁止事項、承認が必要な操作、検証ステータスは他文書と矛盾させないでください。
- エージェント向け入口は短くし、詳細は領域別文書へ分けます。
