import os
import json
import datetime as dt
import logging
import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError

PK = "failover"
RK = "state"

def utc_now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("init: start")

    table = TableServiceClient.from_connection_string(
        os.environ["AzureWebJobsStorage"]
    ).get_table_client(os.environ["STATE_TABLE_NAME"])

    # If already exists -> return idempotent OK
    try:
        existing = table.get_entity(PK, RK)
        return func.HttpResponse(
            json.dumps({
                "initialized": True,
                "already_exists": True,
                "active_target": existing.get("active_target", "primary"),
                "last_status": existing.get("last_status", "")
            }),
            status_code=200,
            mimetype="application/json"
        )
    except ResourceNotFoundError:
        pass

    primary = os.environ.get("PRIMARY_ENDPOINT", "")
    secondary = os.environ.get("SECONDARY_ENDPOINT", "")

    if not primary or not secondary:
        # Strict behavior so Terraform fails early if missing endpoints
        return func.HttpResponse(
            json.dumps({
                "initialized": False,
                "already_exists": False,
                "error": "missing_endpoints",
                "details": {
                    "PRIMARY_ENDPOINT_set": bool(primary),
                    "SECONDARY_ENDPOINT_set": bool(secondary)
                }
            }),
            status_code=400,
            mimetype="application/json"
        )

    entity = {
        "PartitionKey": PK,
        "RowKey": RK,
        "active_target": "primary",
        "primary_endpoint": primary,
        "secondary_endpoint": secondary,
        "last_status": "INIT",
        "last_reason": "initialized_by_init_function",
        "last_check_utc": utc_now_iso(),
        "failover_count": 0,
        "lock_until_utc": ""
    }

    table.create_entity(entity)

    logging.info("init: state entity created (failover/state)")

    return func.HttpResponse(
        json.dumps({
            "initialized": True,
            "already_exists": False,
            "active_target": "primary",
            "table": os.environ["STATE_TABLE_NAME"]
        }),
        status_code=201,
        mimetype="application/json"
    )
