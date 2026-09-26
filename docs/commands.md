# コマンド

前提として、Azure CLI でのサインインと、対象サブスクリプションの選択を済ませてください。

## Azure

```bash
az login
az account set --subscription <subscription-id>
```

## Terraform

```bash
terraform -chdir=envs/dev init
terraform -chdir=envs/dev fmt -recursive
terraform -chdir=envs/dev validate
terraform -chdir=envs/dev plan -var-file=../../environments/dev.tfvars
terraform -chdir=envs/dev apply -var-file=../../environments/dev.tfvars
```

## Functions

リポジトリのルートで Python 3.14 を使います。Windows (PowerShell) では次を実行します。

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install pip==26.1.2
.venv\Scripts\python -m pip install -r functions/sdui_api/requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pip check
.venv\Scripts\python -m ruff format --check functions scripts
.venv\Scripts\python -m ruff check functions scripts
.venv\Scripts\python -m pytest
```

Linux では次を実行します。

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install pip==26.1.2
.venv/bin/python -m pip install -r functions/sdui_api/requirements.txt -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python -m ruff format --check functions scripts
.venv/bin/python -m ruff check functions scripts
.venv/bin/python -m pytest
```

依存バージョンを更新するときは、Python 3.14 の環境に `uv==0.12.19` を導入し、リポジトリのルートで次を実行します。直接依存は `functions/sdui_api/requirements.in` と `requirements-dev.in` で管理します。開発用の入力は本番用の固定ファイルを制約として参照します。Windows (PowerShell) の例:

```powershell
.venv\Scripts\python -m pip install uv==0.12.19
.venv\Scripts\uv pip compile --universal --python-version 3.14 functions/sdui_api/requirements.in -o functions/sdui_api/requirements.txt
.venv\Scripts\uv pip compile --universal --python-version 3.14 requirements-dev.in -o requirements-dev.txt
```

Linux の例:

```bash
.venv/bin/python -m pip install uv==0.12.19
.venv/bin/uv pip compile --universal --python-version 3.14 functions/sdui_api/requirements.in -o functions/sdui_api/requirements.txt
.venv/bin/uv pip compile --universal --python-version 3.14 requirements-dev.in -o requirements-dev.txt
```

生成した `.txt` は手編集しません。入力ファイルの変更や更新オプションの指定がなければ、再生成時は既存の固定バージョンが再利用されます。特定の間接依存を更新する場合は、対象の `uv pip compile` コマンドに `--upgrade-package <package-name>` を追加します。全体の更新が必要な場合に限り `--upgrade` を使います。pip の固定バージョンを変更するときは、この文書、`docs/tech_stack.md`、`.github/workflows/ci.yml` を合わせて更新します。uv の固定バージョンを変更するときは、この文書と `docs/tech_stack.md` を合わせて更新します。

生成後は新しい環境で `pip check`、整形、lint、pytest を実行し、CI の Linux / Windows 両ジョブを確認します。`--universal` はOSごとの条件付き依存を記録しますが、各OSでの実行確認の代わりにはなりません。Azure Functions の remote build で使われる pip のバージョンは、このCI設定では固定できません。

生成方法の詳細は [uvの依存固定ドキュメント](https://docs.astral.sh/uv/pip/compile/) を参照してください。

ローカル実行には Azure Functions Core Tools が必要です。

```bash
func start --script-root functions/sdui_api
```

## Seed

`scripts/seed_cosmos.py` は `seed/ui_definitions/` と `seed/account_profiles/` の全ファイルを検証し、すべて成功した場合だけ Cosmos DB へ upsert します。実行には上記の `requirements.txt` と `requirements-dev.txt` の両方が必要です。

```bash
python scripts/seed_cosmos.py --dry-run
python scripts/seed_cosmos.py --endpoint <cosmos-endpoint>
```

- `--dry-run` は endpoint と Azure の資格情報を必要とせず、Cosmos DB クライアントも生成しません。検証結果と登録予定の件数だけを表示します。
- 通常の登録では `--endpoint` または `COSMOS_ENDPOINT` が必須です。データベース名は `--database` または `COSMOS_DATABASE`（既定 `sdui`）、コンテナー名は `UI_DEFINITIONS_CONTAINER` と `ACCOUNT_PROFILES_CONTAINER` で変更できます。
- 1件でも検証エラーがあれば、何も書き込まずに終了コード 1 で終わります。エラーは相対ファイルパス、文書内の位置（JSON パス）、違反内容の形で表示し、profile の値は表示しません。
- 事前検証は入力不備による途中までの登録を防ぎますが、通信障害時に書き込み全体を原子的にするものではありません。

検証内容は次のとおりです。

| 種類 | 内容 |
|---|---|
| JSON Schema | `seed/schemas/<ディレクトリ名>.schema.json`。必須項目と型を検証し、任意項目の省略、未知の `type`、`props` の未知のキー、文書の未知のフィールドは許容します |
| `ui_definitions` | `id` が `{surface}:{version}` と一致すること。同じ兄弟配列（`components`、各 `children`、各 variant の `components`）で component の `id` が重複しないこと |
| `account_profiles` | `id` が `userId` と一致すること |
| 警告 | `props` の値が object または配列の場合。Android クライアントが破棄するため警告のみとし、登録は止めません |

variant の component が base と同じ `id` を持つのは正当な上書きのため、エラーにしません。

## デプロイ

```bash
func azure functionapp publish sd-ui-api-dev --python
```
