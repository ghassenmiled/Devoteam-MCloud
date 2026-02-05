import os
import json
import datetime as dt
import logging
import requests
import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError

PK = "failover"
RK = "state"

def utc_now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("health_check: start")

    table = TableServiceClient.from_connection_string(
        os.environ["AzureWebJobsStorage"]
    ).get_table_client(os.environ["STATE_TABLE_NAME"])

    try:
        state = table.get_entity(PK, RK)
    except ResourceNotFoundError:
        return func.HttpResponse(
            json.dumps({
                "healthy": False,
                "status": "STATE_NOT_INITIALIZED",
                "reason": "missing_state_entity",
                "action": "Call /api/init first to create failover/state entity"
            }),
            status_code=409,
            mimetype="application/json"
        )


    active_target = state.get("active_target", "primary")
    primary = state.get("primary_endpoint", os.environ.get("PRIMARY_ENDPOINT", ""))
    secondary = state.get("secondary_endpoint", os.environ.get("SECONDARY_ENDPOINT", ""))

    endpoint = primary if active_target == "primary" else secondary

    if not endpoint:
        state["last_status"] = "ERROR"
        state["last_reason"] = "missing_endpoint"
        state["last_check_utc"] = utc_now_iso()
        table.upsert_entity(state)

        return func.HttpResponse(
            json.dumps({
                "healthy": False,
                "active_target": active_target,
                "checked_endpoint": endpoint,
                "reason": "missing_endpoint"
            }),
            status_code=200,
            mimetype="application/json"
        )

    healthy = False
    reason = ""

    try:
        r = requests.get(endpoint, timeout=2)
        healthy = (r.status_code == 200)
        reason = f"http_{r.status_code}"
    except requests.Timeout:
        reason = "timeout"
    except Exception as e:
        reason = f"error:{type(e).__name__}"

    state["last_status"] = "OK" if healthy else "ERROR"
    state["last_reason"] = reason
    state["last_check_utc"] = utc_now_iso()

    table.upsert_entity(state)

    return func.HttpResponse(
        json.dumps({
            "healthy": healthy,
            "active_target": active_target,
            "checked_endpoint": endpoint,
            "reason": reason
        }),
        status_code=200,
        mimetype="application/json"
    )
