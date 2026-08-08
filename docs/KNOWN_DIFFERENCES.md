# Known Differences: Local vs. Real AWS

The local development environment runs on [Floci](https://floci.io/), a local AWS
emulator. This table documents every behaviour that differs between the local
environment and a real AWS account.

| What's different | Local (Floci) | Real AWS | Impact | Workaround |
|---|---|---|---|---|
| **IAM enforcement** | IAM is not enforced; any principal can perform any action | IAM policy is gatekept for every API call | Passing locally proves Spark logic, not IAM policy | Review `terraform/iam.tf` for the intended least-privilege policy |
| **Job bookmarks** | Not implemented — re-running the job re-processes all files | Bookmarks track processed files between runs | Idempotent re-runs are not possible locally | Design the pipeline assuming no bookmark support |
| **Crawlers and StartJobRun** | Not emulated by Floci — schema registration uses the bootstrap script | Crawlers auto-discover schemas; `StartJobRun` is the standard job invocation API | The `bootstrap` step registers schemas via boto3 (`CreateTable`, `CreatePartition`), not a crawler | Run `./run.sh bootstrap` to register schemas |
| **`from_catalog` unavailable** | The Glue Catalog client is JVM closed-source; endpoint redirection is unavailable | `from_catalog` reads directly from the Glue Data Catalog | The job uses explicit `s3a://` paths via `from_options`, not `from_catalog` | No local workaround; `from_catalog` is only available on real AWS |
| **Athena SQL dialect (DuckDB)** | Floci serves Athena through a DuckDB sidecar (`floci-duck`) | Athena uses Trino under the hood | Only a portable SQL subset is guaranteed locally | Keep SQL portable: `SELECT`, `WHERE`, `COUNT`, `AVG`, `GROUP BY`, `ORDER BY` only |
| **Terraform validated but never applied** | `terraform init -backend=false`, `terraform fmt -check`, `terraform validate` run in CI | `terraform apply` requires real credentials and a real account | Passing Terraform checks proves the module is syntactically valid; it does not prove resources work in a real account | Review `terraform/` before applying to a real account |
| **Floci UpdateDatabase / UpdateTable** | Neither operation is implemented by Floci | Both are available in real AWS Glue | Schema edits to a running Floci container are not absorbed without a restart | Run `./run.sh down && ./run.sh up` to restart Floci, then re-bootstrap |
| **`docker compose` outside `run.sh` on Windows** | MSYS2 rewrites POSIX path arguments before Docker sees them, silently misrouting container-side paths | Not affected | Ad-hoc `docker compose` commands with path arguments silently fail on Windows | Always use `./run.sh`, which sets `MSYS_NO_PATHCONV=1` internally |
| **Floci `GetTables` on a nonexistent database** | Returns `[]` (empty list) | Raises `EntityNotFoundException` | A nonexistent database and an empty database are indistinguishable through `GetTables` alone | Confirm the database name is derived correctly via `catalog/config.py` (`PROJECT_NAME.replace('-', '_') + '_db')` |
| **Append mode row duplication** | The job writes in append mode | Same behaviour with append mode | Running `./run.sh demo` twice without stopping the emulator first doubles the row count in each partition | Run `./run.sh down` before re-running, or clear the curated prefix between runs |
