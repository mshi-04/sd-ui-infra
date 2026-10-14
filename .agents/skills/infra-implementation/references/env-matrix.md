# dev / prod の差分と変数の経路

[envs/dev/main.tf](../../../../envs/dev/main.tf) と [envs/prod/main.tf](../../../../envs/prod/main.tf) は
同じ4モジュール（`identity`、`ui_store`、`observability`、`sdui_api`）を同じ順序で呼びます。
差は変数だけです。新しい変数や引数を足すときは、必ず両方を更新します。

## モジュール引数の差

| モジュール | 引数 | dev | prod |
|---|---|---|---|
| `identity` | `app_role_assignment_required` | `false` | `true` |
| `ui_store` | `backup_type` | `"Periodic"` | `"Continuous"` |
| `ui_store` | `continuous_backup_tier` | 渡さない（モジュール既定 `Continuous7Days`） | `"Continuous7Days"` |
| `observability` | `log_retention_in_days` | `30` | `90` |
| `observability` | `alert_email_addresses` | 渡さない（モジュール既定 `[]`） | `var.alert_email_addresses` |
| `sdui_api` | `maximum_instance_count` | `40` | `100` |

次はファイルとして異なる箇所です。

| 項目 | dev | prod |
|---|---|---|
| `locals.env` | `"dev"` | `"prod"` |
| `backend.tf` の `key` | `dev/terraform.tfstate` | `prod/terraform.tfstate` |
| `backend.tf` の `container_name` | `tfstate-dev` | `tfstate-prod` |
| `variables.tf` の `alert_email_addresses` | 宣言しない | 宣言する（既定 `[]`） |
| `*.tfvars.example` | `pre_authorized_client_ids`（Azure CLI の疎通確認用） | `alert_email_addresses` |

`outputs.tf` は両環境で同一です。`backend.tf` の `resource_group_name` と `storage_account_name` は書かず、
`init -backend-config=` で渡します。

## 両環境に共通する値

| 項目 | 値 | 場所 |
|---|---|---|
| Terraform | `1.15.6` | `.terraform-version`、各 root の `required_version` |
| `azurerm` / `azuread` / `random` | `4.58.0` / `3.7.0` / `3.7.2`（`bootstrap` は `random` なし） | 各 root の `required_providers`（完全一致で固定） |
| モジュール側の制約 | `>= 4.58.0`、`>= 3.7.0`、`>= 3.6.0` | `modules/*/main.tf` |
| provider 設定 | `resource_provider_registrations = "none"`、`storage_use_azuread = true` | `envs/*/main.tf` |
| `project_name` | 既定 `sd-ui`（CI / CD は渡さない） | `variables.tf` |

provider のバージョンを上げるときは、各 root の `required_providers` と `.terraform.lock.hcl`、
モジュールの下限制約の整合を確認します。更新は Dependabot も行います。

## 変数の追加経路

`envs/*` の変数は CI では GitHub Actions variables から `TF_VAR_*` で渡します。`.tfvars` はコミットしません。

| Terraform 変数 | PR の plan（`ci.yml`、dev のみ） | CD（`reusable-deploy.yml`） |
|---|---|---|
| `subscription_id` | `AZURE_SUBSCRIPTION_ID` | `AZURE_SUBSCRIPTION_ID` |
| `public_client_redirect_uris` | `DEV_PUBLIC_CLIENT_REDIRECT_URIS` | `PUBLIC_CLIENT_REDIRECT_URIS` |
| `allowed_origins` | `DEV_ALLOWED_ORIGINS` | `ALLOWED_ORIGINS` |
| `app_owner_object_id` | `DEV_APP_OWNER_OBJECT_ID` | `APP_OWNER_OBJECT_ID` |
| `pre_authorized_client_ids` | `DEV_PRE_AUTHORIZED_CLIENT_IDS` | `PRE_AUTHORIZED_CLIENT_IDS` |
| `alert_email_addresses` | 渡さない | `ALERT_EMAIL_ADDRESSES`（未設定なら `[]`） |

変数を足す前に、両環境で使う変数か prod 専用かを決めます。

| 種別 | 変更する箇所 | 前例 |
|---|---|---|
| 両環境用 | `envs/dev` と `envs/prod` の `variables.tf`、両方の `*.tfvars.example`、`ci.yml` の `terraform-plan` の `env`、`reusable-deploy.yml` の `env`、GitHub Actions variables（`DEV_*` と環境スコープ） | `allowed_origins` |
| prod 専用 | `envs/prod/variables.tf`、`environments/prod.tfvars.example`、`reusable-deploy.yml` の `env`、環境スコープの variable。`ci.yml` と dev は触らない（現状、dev は `alert_email_addresses` を宣言しない） | `alert_email_addresses` |

両環境用の順序は次のとおりです。

1. `envs/dev/variables.tf` と `envs/prod/variables.tf` に `description` と `type` 付きで宣言する
2. `environments/dev.tfvars.example` と `environments/prod.tfvars.example` に、ダミー値で追記する
3. `ci.yml` の `terraform-plan` の `env` と、`reusable-deploy.yml` の `env` に `TF_VAR_<name>` を追加する
4. GitHub Actions variables を登録する。PR 用は repository スコープの `DEV_*`、CD 用は environment スコープ（`dev`、`prod`）。コードのマージより前に登録する
5. [docs/infrastructure.md](../../../../docs/infrastructure.md) の GitHub Actions variables 表と環境差分表を更新する
6. 既定値の有無にかかわらず、未登録だと空文字が `TF_VAR_*` に渡され plan が失敗する（`pre_authorized_client_ids` も `[]` を登録する）。number 型は空文字を変換できず全環境の plan が落ちる。`|| '[]'` で補うのは、空が正当な prod 限定の変数に限る

`maximum_instance_count` は既定値なしの必須 `number` です。dev は `40`、prod は `100` をリテラルで渡し、
新しい変数にして調整値を外へ出す場合は、上の経路に従って variable を先に登録します。
値や引数を変えたら `modules/sdui_api/variables.tf` の description（`dev: 40, prod: 100`）、
docs の環境差分表、このファイルの差分表も更新します。

リスト型は `["https://app.example.com"]` の JSON 形式で登録します。値をローカルの tfvars と一致させないと、
CD の apply が差分を適用します（例: 事前承認の削除）。

## CI / CD の実行範囲

| ワークフロー | 契機 | Terraform の内容 |
|---|---|---|
| `ci.yml` `terraform-validate` | PR（`develop`、`main`） | `fmt -check -recursive`、`init -backend=false`、`validate`。matrix は `envs/dev`、`envs/prod`、`bootstrap` |
| `ci.yml` `terraform-plan` | PR | `envs/dev` のみ。`plan -refresh=false -lock=false -input=false`。plan ID（読み取り専用）でサインイン |
| `cd.yml` | `develop` / `main` への push | `reusable-deploy.yml` が `apply -auto-approve`。環境ごとの deploy ID でサインイン |

- prod の plan は PR では実行されません。dev の plan では prod 専用の変更が見えないため、prod に影響する変更は operator が `envs/prod` で plan を取って差分を示します。`main` への反映時に初めて apply されます。取れない場合は未実行と報告します。
- PR の plan は `-refresh=false` のため drift を表示しません。drift は operator が手元で確認します。
- `develop` / `main` へのマージが apply になるため、マージ前に差分を確認し、承認を得ます。`prod` の environment には required reviewers を設定します。
- `bootstrap/` は CD の対象外です。local state で operator が適用します。

## 参考資料

- [docs/infrastructure.md](../../../../docs/infrastructure.md)
- [docs/getting_started.md](../../../../docs/getting_started.md)
- [docs/commands.md](../../../../docs/commands.md)
