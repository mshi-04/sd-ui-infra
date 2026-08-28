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

```bash
python -m venv .venv
.venv/Scripts/pip install -r functions/sdui_api/requirements.txt
.venv/Scripts/pip install pytest ruff
```

```bash
ruff format functions
ruff check functions
pytest
```

ローカル実行には Azure Functions Core Tools が必要です。

```bash
func start --script-root functions/sdui_api
```

## デプロイ

```bash
func azure functionapp publish sd-ui-api-dev --python
```
