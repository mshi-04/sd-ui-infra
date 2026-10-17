# sd-ui-infra

[日本語](README.md) | English

A preserved learning and reference sample of a Server-Driven UI backend on Azure.
It builds UI schemas for an Android application using the roles and account preferences of users authenticated with Microsoft Entra ID.
The companion client is [sd-ui-app](https://github.com/mshi-04/sd-ui-app).

This repository preserves an implementation snapshot; ongoing maintenance and availability of the original cloud environment are not assumed.
It includes a way to try the API without Azure and detailed instructions for setting up your own Azure environment.

The detailed documents also preserve notes about the original development environment. Treat configuration values in the public archive as samples and adapt them to your own environment.

## Implemented behavior

- An Azure Functions / Python `GET /api/ui/{surface}` endpoint. The included UI definition is for `dashboard`.
- Microsoft Entra ID access-token validation, including signature, issuer, audience, and the `UiSchema.Read` scope.
- UI definitions and account profiles stored in Cosmos DB, selecting the latest definition by comparing `version` strings.
- Variants merged according to app roles and profile audiences, followed by entitlement-based component filtering. Profile preferences control theme, density, and pinned component order.
- An `ETag` derived from the resolved schema, with `304` returned for an exact `If-None-Match` match. Production `200` / `304` responses include `Cache-Control: private, max-age=60` by default and `Vary: Authorization`.
- Terraform definitions for dev / prod Azure Functions, Cosmos DB, identity, and monitoring resources.

The production API returns the following responses. See [Client integration (Japanese)](docs/client_integration.md) for the full contract.

| Status | Meaning |
|---|---|
| `200` / `304` | Returns the UI schema / matches the cached representation and returns no body |
| `401` | Invalid token or missing required scope |
| `404` | No definition for the requested surface |
| `500` | Invalid configuration or stored data, a persistent dependency failure, or an unexpected error |
| `503` | Temporary JWKS or Cosmos DB failure |

## Try the API without Azure

Python 3.14 is required. Run the following commands from the repository root.
The mock server uses the included seed data and the same resolver as production. It requires no Azure account, Terraform, or Azure Functions Core Tools.
Installing dependencies requires an internet connection.

Windows / PowerShell:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install pip==26.1.2
.venv\Scripts\python -m pip install -r functions/sdui_api/requirements.txt -r requirements-dev.txt
.venv\Scripts\python scripts/seed_cosmos.py --dry-run
.venv\Scripts\python scripts/dev_server.py --port 8080
```

Linux:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install pip==26.1.2
.venv/bin/python -m pip install -r functions/sdui_api/requirements.txt -r requirements-dev.txt
.venv/bin/python scripts/seed_cosmos.py --dry-run
.venv/bin/python scripts/dev_server.py --port 8080
```

`--dry-run` validates seed documents without connecting to Azure or writing data.
Once the server is running, use another terminal to make these requests.

Windows / PowerShell:

```powershell
curl.exe -i http://127.0.0.1:8080/api/ui/dashboard
curl.exe -i -H "X-Dev-Roles: SupportAgent" http://127.0.0.1:8080/api/ui/dashboard
```

Linux:

```bash
curl -i http://127.0.0.1:8080/api/ui/dashboard
curl -i -H "X-Dev-Roles: SupportAgent" http://127.0.0.1:8080/api/ui/dashboard
```

With the included seed data, the response without headers contains `usage-summary`.
Selecting `SupportAgent` changes its title and adds `impersonation-banner`.
You can also select a seeded profile with `X-Dev-Oid`. The server listens on `127.0.0.1`; stop it with `Ctrl+C`.

The mock skips token validation and takes identity from `X-Dev-Oid` / `X-Dev-Roles`.
It does not reproduce production authentication or external-service failure handling. Some headers also differ, including the absence of production's `Vary: Authorization`. Use it for development.

### Connect the Android application

The base URL from the Android emulator is `http://10.0.2.2:8080/api/`.
See [sd-ui-app](https://github.com/mshi-04/sd-ui-app) for client configuration.
Even with the mock API, the application requires MSAL configuration and sign-in before opening the dashboard.
The application does not send `X-Dev-*` headers, so the mock treats its requests as anonymous.
Running this API locally does not make the complete application usable without Azure.

## Set up your own Azure environment

You need an Azure subscription, an Entra ID tenant, Azure CLI, the Terraform version specified in `.terraform-version`, and Azure Functions Core Tools.
Initial provisioning also requires permissions to manage subscription role assignments and Entra ID applications and permissions.

Follow [Getting started (Japanese)](docs/getting_started.md) to create the state backend and deployment identities, configure the environment, provision resources, seed Cosmos DB, and configure the client.
`environments/*.tfvars.example` and `functions/sdui_api/local.settings.json.example` are configuration templates. Supply values for your own environment and keep real configuration and credentials out of commits.
GitHub Actions definitions include Azure plan / deployment jobs; running them requires your own OIDC and variable configuration.
See [Infrastructure (Japanese)](docs/infrastructure.md) for permissions, CI/CD, and teardown, and [Authentication (Japanese)](docs/auth.md) for identity details.

## Validation

Use the virtual environment created above. The Python checks and seed dry-run do not require an Azure login.

Windows / PowerShell:

```powershell
.venv\Scripts\python -m pip check
.venv\Scripts\python -m ruff format --check functions scripts
.venv\Scripts\python -m ruff check functions scripts
.venv\Scripts\python -m mypy
.venv\Scripts\python -m pytest
.venv\Scripts\python scripts/seed_cosmos.py --dry-run
```

Linux:

```bash
.venv/bin/python -m pip check
.venv/bin/python -m ruff format --check functions scripts
.venv/bin/python -m ruff check functions scripts
.venv/bin/python -m mypy
.venv/bin/python -m pytest
.venv/bin/python scripts/seed_cosmos.py --dry-run
```

Terraform can validate configuration without connecting to the state backend. Downloading providers for the first time requires an internet connection.

```bash
terraform fmt -check -recursive
terraform -chdir=envs/dev init -backend=false
terraform -chdir=envs/dev validate
terraform -chdir=envs/prod init -backend=false
terraform -chdir=envs/prod validate
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
```

pytest replaces Cosmos DB and JWKS communication with test doubles. It does not verify live cloud behavior or HTTP requests through a running Functions host.
`terraform validate` also does not guarantee successful deployment. See [Testing (Japanese)](docs/testing.md) and [Commands (Japanese)](docs/commands.md).

## Repository structure

| Path | Purpose |
|---|---|
| `bootstrap/` | Initial Terraform state backend, per-environment deployment identities, and PR plan identity |
| `modules/` | Reusable Terraform modules |
| `envs/` | dev / prod root modules |
| `environments/` | Environment configuration templates |
| `config/` | App role and entitlement definitions |
| `functions/sdui_api/` | UI schema API and tests |
| `seed/` | UI definitions, account profiles, and JSON Schemas for stored documents |
| `scripts/` | Local mock server and seed validation / import scripts |
| `docs/` | Architecture, API contract, setup, and development conventions |
| `.github/workflows/` | Python / Terraform validation and Azure deployment definitions |

## Limitations

- The included surface is `dashboard`. This repository does not provide business-data APIs or execute component `action` values.
- The Android client supports a limited set of component types and `props` shapes. See [Client integration (Japanese)](docs/client_integration.md) and the client documentation.
- `If-None-Match` uses an exact string comparison. General matching for weak ETags, multiple values, and `*` is not supported.
- Dependencies and cloud configuration reflect the preserved snapshot. Check compatibility and required settings before using current services or tools.

## Documentation

The detailed documents are written in Japanese.

- [Getting started (Japanese)](docs/getting_started.md)
- [Technology stack (Japanese)](docs/tech_stack.md)
- [Architecture (Japanese)](docs/architecture.md)
- [Authentication (Japanese)](docs/auth.md)
- [Client integration (Japanese)](docs/client_integration.md)
- [Infrastructure (Japanese)](docs/infrastructure.md)
- [Coding standards (Japanese)](docs/coding_standards.md)
- [Commands (Japanese)](docs/commands.md)
- [Testing (Japanese)](docs/testing.md)
