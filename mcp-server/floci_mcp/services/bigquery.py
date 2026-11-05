"""BigQuery datasets, tables, inserts and queries.

`bq` CLI commands fail against the emulator (500 on the discovery document),
but the REST surface works, including real SQL execution.
"""

from __future__ import annotations

from typing import Any

from ..client import client, flatten_bq_rows

READ_ONLY = {"readOnlyHint": True}
DESTRUCTIVE = {"destructiveHint": True}


def _base() -> str:
    return f"/bigquery/v2/projects/{client.project}"


def register(mcp: Any) -> None:
    @mcp.tool(
        name="bq_list_datasets",
        description="List BigQuery datasets in the project.",
        annotations=READ_ONLY,
    )
    async def bq_list_datasets() -> Any:
        return await client.get(f"{_base()}/datasets")

    @mcp.tool(
        name="bq_create_dataset",
        description="Create a BigQuery dataset.",
        annotations={"idempotentHint": True},
    )
    async def bq_create_dataset(
        dataset_id: str,
        location: str = "US",
        description: str | None = None,
    ) -> Any:
        body: dict[str, Any] = {
            "datasetReference": {
                "datasetId": dataset_id,
                "projectId": client.project,
            },
            "location": location,
        }
        if description:
            body["description"] = description
        return await client.post(f"{_base()}/datasets", json=body)

    @mcp.tool(
        name="bq_delete_dataset",
        description=(
            "Delete a dataset. Destructive. Pass `delete_contents` to also drop "
            "the tables it holds, which the API otherwise refuses."
        ),
        annotations=DESTRUCTIVE,
    )
    async def bq_delete_dataset(dataset_id: str, delete_contents: bool = False) -> Any:
        client.guard_destructive(f"delete dataset {dataset_id}")
        await client.delete(
            f"{_base()}/datasets/{dataset_id}",
            params={"deleteContents": "true" if delete_contents else None},
        )
        return {"deleted": f"{client.project}:{dataset_id}"}

    @mcp.tool(
        name="bq_list_tables",
        description="List tables in a dataset.",
        annotations=READ_ONLY,
    )
    async def bq_list_tables(dataset_id: str) -> Any:
        return await client.get(f"{_base()}/datasets/{dataset_id}/tables")

    @mcp.tool(
        name="bq_get_table",
        description="Get a table's schema, row count and metadata.",
        annotations=READ_ONLY,
    )
    async def bq_get_table(dataset_id: str, table_id: str) -> Any:
        return await client.get(f"{_base()}/datasets/{dataset_id}/tables/{table_id}")

    @mcp.tool(
        name="bq_create_table",
        description=(
            "Create a table. `schema` is a list of field dicts, e.g. "
            '[{"name": "id", "type": "INTEGER", "mode": "REQUIRED"}, '
            '{"name": "email", "type": "STRING"}]. Types: STRING, INTEGER, '
            "FLOAT, NUMERIC, BOOL, TIMESTAMP, DATE, JSON, RECORD. `mode` "
            "defaults to NULLABLE."
        ),
        annotations={"idempotentHint": True},
    )
    async def bq_create_table(
        dataset_id: str,
        table_id: str,
        schema: list[dict[str, Any]],
    ) -> Any:
        return await client.post(
            f"{_base()}/datasets/{dataset_id}/tables",
            json={
                "tableReference": {
                    "projectId": client.project,
                    "datasetId": dataset_id,
                    "tableId": table_id,
                },
                "schema": {"fields": schema},
            },
        )

    @mcp.tool(
        name="bq_delete_table",
        description="Delete a table and its data. Destructive.",
        annotations=DESTRUCTIVE,
    )
    async def bq_delete_table(dataset_id: str, table_id: str) -> Any:
        client.guard_destructive(f"delete table {dataset_id}.{table_id}")
        await client.delete(f"{_base()}/datasets/{dataset_id}/tables/{table_id}")
        return {"deleted": f"{client.project}:{dataset_id}.{table_id}"}

    @mcp.tool(
        name="bq_insert_rows",
        description=(
            "Stream rows into a table. `rows` is a list of plain dicts keyed by "
            'column name, e.g. [{"id": 1, "email": "a@b.c"}]. Returns any '
            "per-row insert errors the API reports."
        ),
    )
    async def bq_insert_rows(
        dataset_id: str,
        table_id: str,
        rows: list[dict[str, Any]],
    ) -> Any:
        result = await client.post(
            f"{_base()}/datasets/{dataset_id}/tables/{table_id}/insertAll",
            json={"rows": [{"json": row} for row in rows]},
        )
        errors = (result or {}).get("insertErrors", [])
        return {
            "table": f"{client.project}:{dataset_id}.{table_id}",
            "rows_submitted": len(rows),
            "insert_errors": errors,
            "ok": not errors,
        }

    @mcp.tool(
        name="bq_query",
        description=(
            "Run a SQL query and return the rows as plain dicts. Standard SQL "
            "by default. Reference tables as `dataset.table`."
        ),
    )
    async def bq_query(
        sql: str,
        max_results: int = 100,
        use_legacy_sql: bool = False,
    ) -> dict[str, Any]:
        result = await client.post(
            f"{_base()}/queries",
            json={
                "query": sql,
                "useLegacySql": use_legacy_sql,
                "maxResults": max_results,
            },
        )
        rows = flatten_bq_rows(result.get("schema"), result.get("rows"))
        return {
            "job_complete": result.get("jobComplete"),
            "total_rows": result.get("totalRows"),
            "schema": [f.get("name") for f in (result.get("schema") or {}).get("fields", [])],
            "rows": rows,
            "errors": result.get("errors"),
        }
