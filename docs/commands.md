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

リポジトリのルートで Python 3.12 を使います。Windows (PowerShell) では次を実行します。

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install pip==26.1.2
.venv\Scripts\python -m pip install -r functions/sdui_api/requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pip check
.venv\Scripts\python -m ruff format --check functions scripts
.venv\Scripts\python -m ruff check functions scripts
.venv\Scripts\python -m pytest
```

Linux では次を実行します。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install pip==26.1.2
.venv/bin/python -m pip install -r functions/sdui_api/requirements.txt -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python -m ruff format --check functions scripts
.venv/bin/python -m ruff check functions scripts
.venv/bin/python -m pytest
```

依存バージョンを更新するときは、Python 3.12 の環境に `uv==0.12.19` を導入し、リポジトリのルートで次を実行します。直接依存は `functions/sdui_api/requirements.in` と `requirements-dev.in` で管理します。開発用の入力は本番用の固定ファイルを制約として参照します。Windows (PowerShell) の例:

```powershell
.venv\Scripts\python -m pip install uv==0.12.19
.venv\Scripts\uv pip compile --universal --python-version 3.12 functions/sdui_api/requirements.in -o functions/sdui_api/requirements.txt
.venv\Scripts\uv pip compile --universal --python-version 3.12 requirements-dev.in -o requirements-dev.txt
```

Linux の例:

```bash
.venv/bin/python -m pip install uv==0.12.19
.venv/bin/uv pip compile --universal --python-version 3.12 functions/sdui_api/requirements.in -o functions/sdui_api/requirements.txt
.venv/bin/uv pip compile --universal --python-version 3.12 requirements-dev.in -o requirements-dev.txt
```

生成した `.txt` は手編集しません。入力ファイルの変更や更新オプションの指定がなければ、再生成時は既存の固定バージョンが再利用されます。特定の間接依存を更新する場合は、対象の `uv pip compile` コマンドに `--upgrade-package <package-name>` を追加します。全体の更新が必要な場合に限り `--upgrade` を使います。pip の固定バージョンを変更するときは、この文書、`docs/tech_stack.md`、`.github/workflows/ci.yml` を合わせて更新します。uv の固定バージョンを変更するときは、この文書と `docs/tech_stack.md` を合わせて更新します。

生成後は新しい環境で `pip check`、整形、lint、pytest を実行し、CI の Linux / Windows 両ジョブを確認します。`--universal` はOSごとの条件付き依存を記録しますが、各OSでの実行確認の代わりにはなりません。Azure Functions の remote build で使われる pip のバージョンは、このCI設定では固定できません。

生成方法の詳細は [uvの依存固定ドキュメント](https://docs.astral.sh/uv/pip/compile/) を参照してください。

ローカル実行には Azure Functions Core Tools が必要です。

```bash
func start --script-root functions/sdui_api
```

## デプロイ

```bash
func azure functionapp publish sd-ui-api-dev --python
```
