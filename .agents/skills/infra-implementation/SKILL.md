---
name: infra-implementation
description: Terraform / Azure インフラ（modules・envs・bootstrap のリソース追加と変更、Entra ID アプリ登録、managed identity と RBAC、tfvars.example と GitHub Actions variables、plan / apply）の設計・実装・修正に使う。dev / prod の差分表、変数の追加経路、承認が必要な操作、CI と同じ検証フローを提供。
---

# Infra Implementation

## 実装手順

1. 変更対象（`modules/*`、`envs/*`、`bootstrap/`、`config/app_roles.json`、workflow）と影響環境を特定する。`modules/identity` と `bootstrap/` はテナント・サブスクリプション全体へ影響するため、実装前に方針をユーザーへ示す。
2. モジュールは `main.tf` / `variables.tf` / `outputs.tf` の構成にし、`provider` ブロックと `var.env` による分岐を置かない。差は `envs/*/main.tf` から変数で渡す。
3. 変数に `description` と `type` を付け、不正値は `validation` で防ぐ。機密値の output は `sensitive = true` にする（`modules/observability/outputs.tf` 参照）。スケール上限を上げるときは Cosmos DB serverless の上限と 429 / 503、リージョンのクォータも確認する。
4. 命名の基本形は `{project_name}-{role}-{env}`。Storage Account は連結形（`modules/sdui_api/main.tf` の `local.storage_account_name`）、リソースグループは `{project_name}-{env}-rg` で `bootstrap/` が作る。Key Vault など名前制約のあるリソースは `references/module-wiring.md` の命名表を確認する。
5. Azure リソース間の認可は managed identity と組み込みロールで、スコープを対象リソースまで絞る。アプリに `Owner` / `Contributor` を付けない。`azurerm_role_assignment` に新しいロールを使う場合は、先に `bootstrap/variables.tf` の `ci_assignable_role_definition_ids` へ追加して operator が apply する（承認必須。詳細は module-wiring.md）。ユーザーへの app role 割り当ては Terraform に入れない。
6. タグは `bootstrap/` のリソースグループにだけ付け、モジュール内に書かない。`envs/*` は `resource_provider_registrations = "none"` のため、新しい種類のリソースは先に `bootstrap/main.tf` の `resource_providers_to_register`（現在の一覧は module-wiring.md）へ追加し、承認を得て apply してから envs の PR をマージする（マージが apply になる）。
7. `envs/dev` と `envs/prod` は同時に更新し、差分は `references/env-matrix.md` の表と照合する。値や引数を変えたら `variables.tf` の description と env-matrix.md も更新する。
8. 新しい変数は、両環境用か prod 専用かを先に決め、env-matrix.md の「変数の追加経路」に従って `variables.tf`、`*.tfvars.example`、workflow の `TF_VAR_*`、GitHub Actions variables を揃える。variable はマージ前に登録する（未登録は空文字になり plan が失敗する）。`docs/infrastructure.md` は variables 表と環境差分表の両方を更新する。
9. SCM basic 認証・Storage のキー認証・Cosmos DB のローカル認証は無効のまま保つ。PR の plan ID が dev の state を読めるため、secret の値を tfvars、variable、output、state に入れない（Key Vault は本体と RBAC のみ Terraform、値は operator が投入する）。
10. リソース名・`for_each` キー・モジュールパスを変える場合は置換になるか plan で確認し、通常は `moved` ブロックで移す。`terraform state mv` は state を直接変更するため、対象アドレスを示して承認を得てから実行する。新しいモジュールを足したら `docs/infrastructure.md` のモジュール表、`docs/tech_stack.md`、module-wiring.md を更新し、dev と prod の両方から呼ぶ。新しい root module は `.github/dependabot.yml` と `ci.yml` の matrix にも追加する。
11. 承認必須操作（`terraform apply`、削除・置換・destroy を含む plan、`bootstrap/` の変更、Cosmos DB への実書き込み）は、差分を示してユーザーの明示的な承認を得てから実行する。`modules/identity` を含む plan は差分を提示してから apply する。`develop` / `main` へのマージは CD の apply になるため、マージ前に差分を示して承認を得る。
12. app settings を追加・変更したら `functions/sdui_api/settings.py`、`local.settings.json.example`、テストを `api-implementation` で更新する。`config/app_roles.json` に触れる場合は `app-role-implementation` を参照する。

## 検証手順

1. `terraform fmt -check -recursive`
2. `envs/dev`、`envs/prod`、`bootstrap` の各ディレクトリで `terraform -chdir=<dir> init -backend=false` と `terraform -chdir=<dir> validate`
3. 資格情報とバックエンドが使える場合のみ plan を取る。`environments/<env>.tfvars` は `.example` からコピーし（コミットしない）、`init` は `-backend-config` で渡してから `terraform -chdir=envs/<env> plan -var-file=../../environments/<env>.tfvars`（手順は `docs/getting_started.md` の「4. 環境の適用」）。PR の plan は dev のみのため、prod に影響する変更は operator が `envs/prod` で plan を取り、差分をユーザーに示してから `main` へ反映する。取れなければ未実行と報告する。
4. 完了報告は検証ステータス（実行して成功 / 未実行 / 資格情報や state の都合で実行不可）を明記する。

## 参考資料

- [references/module-wiring.md](references/module-wiring.md): モジュールの責務と配線、命名、RBAC、bootstrap の権限境界、置換・state 移動の注意
- [references/env-matrix.md](references/env-matrix.md): dev / prod の差分表、変数と GitHub Actions variables の対応、CI / CD の実行範囲
- [docs/infrastructure.md](../../../docs/infrastructure.md)
- [docs/coding_standards.md](../../../docs/coding_standards.md)
- [docs/commands.md](../../../docs/commands.md)
- [docs/getting_started.md](../../../docs/getting_started.md)
- [docs/tech_stack.md](../../../docs/tech_stack.md)
