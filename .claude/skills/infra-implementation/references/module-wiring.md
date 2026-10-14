# モジュールの配線と権限境界

各モジュールは `main.tf` / `variables.tf` / `outputs.tf` の3ファイルで構成し、`provider` ブロックを持ちません。
`main.tf` 冒頭の `required_providers` でバージョンの下限（`>=`）だけを宣言します。

## モジュールの責務

| モジュール | 主なリソース | 注意点 |
|---|---|---|
| `identity` | `azuread_application`（api / client）、`azuread_service_principal`、`azuread_application_pre_authorized`、`random_uuid` | `azurerm` を使わない。`api` アプリは `lifecycle.ignore_changes = [identifier_uris]` と別リソース `azuread_application_identifier_uri` を組み合わせる |
| `ui_store` | Cosmos DB account、database、container（`ui_definitions`、`account_profiles`） | `local_authentication_disabled = true`、serverless。`backup_type` は環境から渡す |
| `observability` | Log Analytics workspace、Application Insights、action group、5xx アラート | `alert_email_addresses` が空ならアラート系は `count = 0`。接続文字列の output は `sensitive = true` |
| `sdui_api` | Storage Account、`deployments` コンテナ、Service Plan（`FC1`）、Function App（Flex Consumption）、role assignment、診断設定 | `shared_access_key_enabled = false`、`webdeploy_publish_basic_authentication_enabled = false` |

## 配線の流れ

`envs/*/main.tf` が、モジュール間の値を output から input へつなぎます。

| 出力元 | 出力 | 受け取り先 |
|---|---|---|
| `identity` | `tenant_id`、`api_client_id`、`ui_schema_read_scope`、`role_entitlements` | `sdui_api` の `tenant_id`、`api_client_id`、`required_scope`、`role_entitlements` |
| `ui_store` | `account_id`、`account_name`、`endpoint`、`database_name`、各 container 名 | `sdui_api` の `cosmos_*`、container 名 |
| `observability` | `application_insights_connection_string`、`workspace_id` | `sdui_api` の同名系変数 |

`sdui_api` はこれらを Function App の `app_settings`（`ENTRA_TENANT_ID`、`COSMOS_ENDPOINT` など）へ展開します。
app settings を追加・変更・改名するときは、`functions/sdui_api/settings.py` の読み取り側と合わせます（`api-implementation` を参照）。
`config/app_roles.json` は `envs/*` が `jsondecode(file(...))` で読んで `identity` の `app_roles` へ渡し、`sdui_api` には `identity` の `role_entitlements` output 経由で渡ります。
app role の追加と削除の扱いは `app-role-implementation` を参照します。

## 命名

| 種類 | 形式 | 例（dev） |
|---|---|---|
| 基本形 | `{project_name}-{role}-{env}` | `sd-ui-cosmos-dev`、`sd-ui-api-dev`、`sd-ui-plan-dev`、`sd-ui-logs-dev` |
| Storage Account | `substr("${replace(project_name, "-", "")}api${env}", 0, 24)` | `sduiapidev` |
| リソースグループ | `{project_name}-{env}-rg`（`bootstrap/` が作成し `envs/*` は `data` 参照） | `sd-ui-dev-rg` |
| Entra ID アプリ | `{project_name}-api-{env}`、`{project_name}-client-{env}` | `sd-ui-api-dev` |
| Key Vault（未導入） | グローバル一意・3〜24文字 | soft delete により destroy 後の同名再作成が衝突し得る。撤去手順の更新も要る |

Storage Account 名は24文字で切り詰めます。`project_name` を長くすると、環境の違いが切り落とされて衝突し得ます。

## 認可と RBAC

- アプリの認可は managed identity と組み込みロールを使います。`sdui_api` は Function App に `SystemAssigned` を付け、次を割り当てます。

  | 付与先スコープ | ロール | リソース |
  |---|---|---|
  | `azurerm_storage_account.api.id` | `Storage Blob Data Owner` | `azurerm_role_assignment.api_storage_blob` |
  | Cosmos DB account | 組み込みの Data Reader（定義ID末尾 `...0001`） | `azurerm_cosmosdb_sql_role_assignment.api_reader` |

- Key Vault の secret を読むロール（`Key Vault Secrets User` など）も同じ制約を受けます。先に `bootstrap/variables.tf` の一覧へ追加して operator が apply し、その後に envs の変更をマージします。
- secret の値は Terraform で管理しません。deploy ID は管理プレーンの `Contributor` のみで、値を Terraform に入れると state に残り、dev の state を読める plan ID から見えます。Key Vault 本体と RBAC だけを Terraform で作り、値は operator が投入し、app settings には Key Vault reference だけを渡します。
- Cosmos DB の data plane ロールは `azurerm_cosmosdb_sql_role_assignment` で付与します。`Owner` / `Contributor` は付けません。
- Function App の Storage 接続は `AzureWebJobsStorage__accountName`（identity ベース）で、接続文字列を使いません。
- deploy ID の `Role Based Access Control Administrator` は、`ci_assignable_role_definition_ids`（`Storage Blob Data Owner` と `Storage Blob Data Contributor`）にある組み込みロールの割り当て・削除だけを許す条件付きです。
  `azurerm_role_assignment` に新しいロールを足すと、CD の apply が認可エラーになります。
  その場合は `bootstrap/variables.tf` の一覧を変更する必要があり、`bootstrap/` の変更として承認を得ます。
  Cosmos DB の data plane ロールは `Microsoft.Authorization` ではないため、この制約の対象外です。

## bootstrap と envs の境界

| 内容 | 管理元 |
|---|---|
| state 用 Storage Account / コンテナ、ワークロード用リソースグループ、リソースプロバイダー登録 | `bootstrap/`（local state、operator が適用） |
| deploy ID（環境ごと）、plan ID、federated credential、RBAC、Graph の `Application.ReadWrite.OwnedBy` | `bootstrap/` |
| Entra ID の API / client アプリ、Cosmos DB、Function App など | `envs/*`（CD が apply） |
| ユーザーへの app role 割り当て | Terraform の対象外（operator が Entra 管理センターまたは CLI で実施） |

`resource_providers_to_register` の現在の一覧は `Microsoft.AlertsManagement`、`Microsoft.DocumentDB`、`Microsoft.Insights`、
`Microsoft.OperationalInsights`、`Microsoft.Storage`、`Microsoft.Web` です。
`envs/*` で別の種類のリソースを使うと、登録が無いために CD が失敗します。先に `bootstrap/` を更新し、承認を得て apply します。`bootstrap/` は CD の対象外で、envs の PR をマージすると apply されるため、順序を守ります。

`azuread_application.*.owners` には環境の deploy サービスプリンシパルを入れます（`app_owner_object_id`）。
`Application.ReadWrite.OwnedBy` は owner のアプリしか管理できないためです。

## 置換と state 移動

- 名前・`for_each` のキー・モジュールパスの変更は、plan で `must be replaced` / `destroy` になるか確認します。
  純粋なリネームは `moved` ブロックか `terraform state mv` で state を移します。判断がつかなければユーザーに確認します。
- `config/app_roles.json` のキーは `random_uuid.app_role` の `for_each` キーです。キーを変えると app role の id が変わり、
  既存のユーザー割り当てを引き継げません。
- Cosmos DB の `partition_key_paths` と container 名の変更は container の置換になり、データを失います。
- `azuread_application.api` の `identifier_uris` は `ignore_changes` 対象です。変更は `azuread_application_identifier_uri` 側で行います。
- スケール上限を上げると Cosmos DB serverless への負荷が増え、429 は API で 503 になります。リージョンの Flex Consumption クォータも確認します。
- Terraform は削除保護も `prevent_destroy` も管理ロックも設定していません。`destroy` や置換は止まらないため、事前に差分を確認します。
- 撤去は `envs/prod` と `envs/dev` の destroy の後に `bootstrap/` を destroy します。destroy は承認必須です。`Application Insights Smart Detection` action group の手動削除など前提作業と順序は [docs/infrastructure.md](../../../../docs/infrastructure.md) の「環境の撤去」を参照します。

## 検証の補足

- `terraform validate` はバックエンド不要の `init -backend=false` で動きます。`plan` には Azure の資格情報と state へのアクセスが必要です。
- `plan` を実行できなかった場合は、理由（資格情報なし、state ロック、未サインインなど）を添えて「未実行」と報告します。
- 検証は CI と同じ範囲に揃えます。範囲は [env-matrix.md](env-matrix.md) の「CI / CD の実行範囲」を参照します。

## 参考資料

- [docs/infrastructure.md](../../../../docs/infrastructure.md)
- [docs/coding_standards.md](../../../../docs/coding_standards.md)
- [docs/auth.md](../../../../docs/auth.md)
