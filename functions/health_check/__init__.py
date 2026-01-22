import os
import json
import datetime as dt
import logging
import requests
import azure.functions as func
from azure.data.tables import TableServiceClient

PK = "failover"
RK = "state"

def utc_now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("health_check: start")

    table = TableServiceClient.from_connection_string(
        os.environ["AzureWebJobsStorage"]
    ).get_table_client(os.environ["STATE_TABLE_NAME"])

    state = table.get_entity(PK, RK)

    active_target = state.get("active_target", "primary")
    primary = state["primary_endpoint"]
    secondary = state["secondary_endpoint"]
    endpoint = primary if active_target == "primary" else secondary

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

    logging.info("health_check: active_target=%s healthy=%s reason=%s", active_target, healthy, reason)

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
