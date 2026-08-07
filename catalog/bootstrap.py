"""Idempotent Data Catalog registration: database, table, and partitions.

Runs inside the `tools` service (python:3.11-slim + boto3), never inside the
Glue container. It makes only boto3 API calls and never touches Spark;
running it on the Glue image would force every adopter to pull roughly
4.8 GB before their first API call, which attacks the project's core value
directly.

Idempotency strategy is create-if-absent, update-if-present (D-08): a
second run applies a schema edit rather than erroring, and never deletes
anything. Partitions are registered one at a time, in a loop, with
`create_partition` because Floci's Glue surface does not implement the
batched form of that operation
(https://floci.io/floci/services/glue/ confirms `BatchCreatePartition` is
absent). A loop is also forward-compatible with real AWS, which supports
both forms. Do not replace this loop with the batched call.

The `Location` written for the table and every partition uses the `s3://`
scheme, not `s3a://`. Real AWS Glue and the Phase 3 Terraform both write
`s3://` into a table's Location; writing anything else here would create
exactly the local/prod divergence CAT-03 exists to prevent. `s3a://` belongs
to Spark's filesystem access in Phase 2, a different concern from catalog
metadata.

KNOWN DIFFERENCE (materialized during 01-03, resolved by operator decision,
carried forward to Phase 4 docs/KNOWN_DIFFERENCES.md): D-08 assumed Glue's
`UpdateDatabase`/`UpdateTable`. Floci v1.5.11 implements neither - both
return `InvalidAction`, matching the operation list PROJECT.md already
records (no `Update*` verb appears there for Glue). `update_database` and
`update_table` remain in the call path below because they are correct
against real AWS Glue and that is what keeps the Phase 3 Terraform path
honest. Against Floci specifically, `InvalidAction` is caught, the current
catalog object is compared against the desired one, and a drift warning
(not a silent success) is logged when they differ. Locally, applying a
schema edit therefore requires restarting the emulator
(`./run.sh down && ./run.sh up`) rather than a bare `bootstrap` re-run -
cheap and correct because `FLOCI_STORAGE_MODE=memory` already makes every
restart a fresh catalog. Any other `ClientError` from the update call (bad
credential, wrong endpoint, ...) is never swallowed - it propagates.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from botocore.exceptions import ClientError

# Running this file as `python catalog/bootstrap.py` (the exact invocation
# run.sh uses) puts the script's own directory (.../catalog) on sys.path[0],
# not the repository root - so a bare `from catalog import config` would
# fail with ModuleNotFoundError. Insert the repository root explicitly so
# the package-qualified import works regardless of invocation style.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog import config  # noqa: E402

logger = logging.getLogger(__name__)

REQUIRED_STORAGE_KEYS = ("input_format", "output_format", "serde")


class SchemaError(Exception):
    """Raised when the schema JSON is structurally invalid."""


def validate_schema(schema: dict) -> None:
    """Raise SchemaError naming the offending key when the schema is invalid.

    An empty `partitions` array is NOT an error - it is a legitimate
    unpartitioned table, and the caller reports "0 partitions registered"
    and exits 0.
    """
    for key in ("table", "bucket", "location"):
        if not schema.get(key):
            raise SchemaError(f"Schema is invalid: '{key}' is missing or empty.")

    if not schema.get("columns"):
        raise SchemaError("Schema is invalid: 'columns' is missing or empty.")

    if not schema.get("partition_keys"):
        raise SchemaError("Schema is invalid: 'partition_keys' is missing.")

    storage = schema.get("storage") or {}
    missing_storage = [k for k in REQUIRED_STORAGE_KEYS if not storage.get(k)]
    if missing_storage:
        raise SchemaError(f"Schema is invalid: 'storage' is missing {missing_storage}.")

    partition_key_count = len(schema["partition_keys"])
    for entry in schema.get("partitions", []):
        values = entry.get("values", [])
        if len(values) != partition_key_count:
            raise SchemaError(
                f"Schema is invalid: partition entry {entry!r} has "
                f"{len(values)} value(s), expected {partition_key_count} "
                "to match 'partition_keys'."
            )


def build_table_input(schema: dict, location_uri: str) -> dict:
    """Map the neutral schema shape to the Glue API TableInput dictionary."""
    storage = schema["storage"]
    return {
        "Name": schema["table"],
        "Description": schema.get("description", ""),
        "TableType": "EXTERNAL_TABLE",
        "Parameters": schema.get("table_parameters", {}),
        "PartitionKeys": [
            {"Name": key["name"], "Type": key["type"]} for key in schema["partition_keys"]
        ],
        "StorageDescriptor": {
            "Columns": [{"Name": col["name"], "Type": col["type"]} for col in schema["columns"]],
            "Location": location_uri,
            "InputFormat": storage["input_format"],
            "OutputFormat": storage["output_format"],
            "SerdeInfo": {"SerializationLibrary": storage["serde"]},
        },
    }


def ensure_database(glue, name: str, description: str) -> str:
    """Create the database, or update it if it already exists.

    `update_database` stays in the call path because it is correct against
    real AWS Glue. Floci does not implement it (`InvalidAction`); when that
    specific error is caught, the current database is compared against the
    desired one and a drift warning is logged rather than the failure being
    swallowed. Any other ClientError (bad credential, wrong endpoint, ...)
    is never caught here - it propagates. Returns "created", "updated", or
    "present" (backend cannot update in place).
    """
    try:
        glue.create_database(DatabaseInput={"Name": name, "Description": description})
        return "created"
    except glue.exceptions.AlreadyExistsException:
        pass

    try:
        glue.update_database(Name=name, DatabaseInput={"Name": name, "Description": description})
        return "updated"
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "InvalidAction":
            raise
        current = glue.get_database(Name=name)["Database"]
        if current.get("Description", "") == description:
            logger.info("database '%s' already current", name)
        else:
            logger.warning(
                "database '%s' exists with a description that differs from the schema JSON "
                "(current=%r, desired=%r), and this catalog backend does not support "
                "in-place update. Restart the emulator to apply the change: "
                "./run.sh down && ./run.sh up",
                name,
                current.get("Description", ""),
                description,
            )
        return "present (backend does not support in-place update)"


def ensure_table(glue, database: str, table_input: dict) -> str:
    """Create the table, or update it if it already exists.

    `update_table` stays in the call path because it is correct against
    real AWS Glue. Floci does not implement it (`InvalidAction`); when that
    specific error is caught, the current table's columns are compared
    (name + type, in order) against the desired ones and a drift warning is
    logged rather than the failure being swallowed. Never deletes and
    recreates: that would be destructive if this script were ever pointed
    at a real AWS account. Any other ClientError (bad credential, wrong
    endpoint, ...) is never caught here - it propagates. Returns "created",
    "updated", or "present" (backend cannot update in place).
    """
    try:
        glue.create_table(DatabaseName=database, TableInput=table_input)
        return "created"
    except glue.exceptions.AlreadyExistsException:
        pass

    try:
        glue.update_table(DatabaseName=database, TableInput=table_input)
        return "updated"
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "InvalidAction":
            raise
        name = table_input["Name"]
        current = glue.get_table(DatabaseName=database, Name=name)["Table"]
        current_columns = [(c["Name"], c["Type"]) for c in current["StorageDescriptor"]["Columns"]]
        desired_columns = [
            (c["Name"], c["Type"]) for c in table_input["StorageDescriptor"]["Columns"]
        ]
        if current_columns == desired_columns:
            logger.info("table '%s' already current", name)
        else:
            logger.warning(
                "table '%s' exists with columns that differ from "
                "catalog/schema/temperaturas.json (current=%r, desired=%r), and this catalog "
                "backend does not support in-place update. Restart the emulator to apply the "
                "change: ./run.sh down && ./run.sh up",
                name,
                current_columns,
                desired_columns,
            )
        return "present (backend does not support in-place update)"


def ensure_partitions(glue, database: str, table: str, schema: dict, location_uri: str) -> tuple:
    """Register every partition in `schema["partitions"]`, one call per partition.

    On AlreadyExistsException for a given partition, skip it and continue:
    partitions are left in place by decision (D-08), unlike the table.
    Returns (created_count, skipped_count).
    """
    storage = schema["storage"]
    partition_keys = [key["name"] for key in schema["partition_keys"]]
    storage_descriptor_template = {
        "Columns": [{"Name": col["name"], "Type": col["type"]} for col in schema["columns"]],
        "InputFormat": storage["input_format"],
        "OutputFormat": storage["output_format"],
        "SerdeInfo": {"SerializationLibrary": storage["serde"]},
    }

    created = 0
    skipped = 0
    for entry in schema.get("partitions", []):
        values = entry["values"]
        segments = "/".join(f"{k}={v}" for k, v in zip(partition_keys, values, strict=True))
        partition_location = f"{location_uri}{segments}/"

        partition_input = {
            "Values": values,
            "StorageDescriptor": {
                **storage_descriptor_template,
                "Location": partition_location,
            },
        }
        try:
            glue.create_partition(
                DatabaseName=database, TableName=table, PartitionInput=partition_input
            )
            created += 1
        except glue.exceptions.AlreadyExistsException:
            skipped += 1

    return created, skipped


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    schema = config.load_schema("catalog/schema/temperaturas.json")

    try:
        validate_schema(schema)
    except SchemaError as exc:
        print(f"[FAIL] schema validation: {exc}", file=sys.stderr)
        return 1

    database = config.database_name()
    curated_bucket = config.curated_bucket()
    location_uri = f"s3://{curated_bucket}/{schema['location']}"

    glue = config.glue_client()

    db_result = ensure_database(glue, database, schema.get("description", ""))
    print(f"[ok] database '{database}': {db_result}")

    table_input = build_table_input(schema, location_uri)
    table_result = ensure_table(glue, database, table_input)
    print(f"[ok] table '{schema['table']}': {table_result}")

    created, skipped = ensure_partitions(glue, database, schema["table"], schema, location_uri)
    if not schema.get("partitions"):
        print("[ok] partitions: 0 partitions registered (table is unpartitioned)")
    else:
        print(f"[ok] partitions: {created} created, {skipped} already present")

    return 0


if __name__ == "__main__":
    sys.exit(main())
