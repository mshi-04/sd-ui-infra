# セットアップ

この文書は、Azure テナントが未作成の状態から dev 環境を動かすまでの順序を定義します。

## Azure なしで実行できる検証

テナントとサブスクリプションが無くても、次は実行できます。CIの `python` と `terraform-validate` も同じ範囲です。

```bash
terraform fmt -check -recursive
terraform -chdir=envs/dev init -backend=false
terraform -chdir=envs/dev validate
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
ruff check functions scripts
python -m mypy
pytest
python scripts/seed_cosmos.py --dry-run
```

`terraform plan`、`terraform apply`、Functions のデプロイはサブスクリプションが必要です。

## 1. テナントとサブスクリプション

Azure サブスクリプションを作成すると Entra ID テナントが紐づきます。既存テナントを使う場合は不要です。
作成後、テナントIDとサブスクリプションIDを確認します。

```bash
az login
az account show --query "{tenantId:tenantId, subscriptionId:id, name:name}"
```

`bootstrap/` は Entra ID のアプリケーションを作成するため、実行者に次が必要です。

- サブスクリプションの `Owner`（ロール割り当てを作成するため）
- Entra ID の `Application Administrator` 以上（アプリケーション登録を作成するため）
- Entra ID の `Privileged Role Administrator` または `Global Administrator`（deploy ID に Microsoft Graph のアプリケーション権限を付与するため）

## 2. bootstrap

state backend、ワークロード用リソースグループ、環境ごとのデプロイ用 ID、PR の plan 用 ID を作ります。resource provider の登録も行います。local state で1度だけ実行します。

```bash
terraform -chdir=bootstrap init
terraform -chdir=bootstrap apply -var="subscription_id=<subscription-id>" -var="github_repository=<owner>/<name>"
```

次の出力を控えます。

- `tfstate_storage_account_name`、`tfstate_resource_group_name`、`tenant_id`
- `deploy_client_ids`（dev と prod）
- `deploy_service_principal_object_ids`（dev と prod）
- `plan_client_id`

`tfstate_container_names` は環境ごとのコンテナ名で、`envs/*/backend.tf` の値と一致します。

state 用ストレージはキー認証を無効にしているため、`bootstrap` は実行者へ `Storage Blob Data Owner` を
付与します。別の担当者が `envs/*` を操作する場合は、同じロールを追加してください。

## 3. GitHub Actions の変数

[docs/infrastructure.md](infrastructure.md) の表にある variables を登録します。

1. GitHub Environment の `dev` と `prod` を作成し、deployment branch policy を `dev` は `develop`、`prod` は `main` に限定する
2. `develop` と `main` への直接 push を禁止する
3. repository スコープに `AZURE_PLAN_CLIENT_ID`（`plan_client_id`）と `DEV_APP_OWNER_OBJECT_ID`（dev の `deploy_service_principal_object_ids`）などを登録する
4. 各 Environment に、その環境の `AZURE_CLIENT_ID`（`deploy_client_ids`）と `APP_OWNER_OBJECT_ID`（`deploy_service_principal_object_ids`）などを登録する。`AZURE_CLIENT_ID` を repository スコープに登録しない
5. `prod` に required reviewers を設定する（private リポジトリでは GitHub Enterprise が必要）

## 4. 環境の適用

```bash
cp environments/dev.tfvars.example environments/dev.tfvars
terraform -chdir=envs/dev init \
  -backend-config="resource_group_name=<tfstate-resource-group>" \
  -backend-config="storage_account_name=<tfstate-storage-account>"
terraform -chdir=envs/dev plan -var-file=../../environments/dev.tfvars
terraform -chdir=envs/dev apply -var-file=../../environments/dev.tfvars
```

`environments/*.tfvars` は `.gitignore` の対象です。コミットしないでください。

`app_owner_object_id` には、その環境の deploy サービスプリンシパルの object id（bootstrap の `deploy_service_principal_object_ids`）を指定します。

## 5. UI定義の投入

Cosmos DB はキー認証を無効にしているため、投入する実行者に data plane のロールが必要です。

```bash
az cosmosdb sql role assignment create \
  --account-name sd-ui-cosmos-dev \
  --resource-group sd-ui-dev-rg \
  --role-definition-id 00000000-0000-0000-0000-000000000002 \
  --principal-id "$(az ad signed-in-user show --query id -o tsv)" \
  --scope "/"
```

```bash
export COSMOS_ENDPOINT="$(terraform -chdir=envs/dev output -raw cosmos_endpoint)"
export COSMOS_DATABASE=sdui
python scripts/seed_cosmos.py --dry-run
python scripts/seed_cosmos.py
```

`seed/account_profiles/example.json` の `id` と `userId` は、対象ユーザーの Entra ID `oid` に置き換えてください。
`--dry-run` は Cosmos DB へ接続せずに全ファイルを検証します。検証エラーが1件でもあれば、登録は何も書き込まずに失敗します。詳細は [docs/commands.md](commands.md) の Seed を参照してください。

## 6. 動作確認

dev では Azure CLI を `pre_authorized_client_ids` に登録しているため、同意なしでトークンを取得できます。
prod では登録しないため、この確認は行えません。

```bash
az account get-access-token --resource "api://$(terraform -chdir=envs/dev output -raw entra_api_client_id)" --query accessToken -o tsv
```

```bash
curl -H "Authorization: Bearer <access-token>" \
  "$(terraform -chdir=envs/dev output -raw api_base_url)/ui/dashboard"
```

app role を割り当てていないユーザーでは variant が適用されません。
出し分けを確認する場合は、Entra 管理センターまたは CLI で `SupportAgent` を割り当てるか、account profile の `audiences` に追加します。
app role の割り当ては Terraform の管理対象外です。

## 撤去

環境を片付ける手順は [docs/infrastructure.md](infrastructure.md) の「環境の撤去」を参照してください。
