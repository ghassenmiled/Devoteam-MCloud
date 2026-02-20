import os, json, logging, datetime as dt
import requests
import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError

PK = "failover"
RK = "state"

def utc_now_iso():
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
            json.dumps({"healthy": False, "reason": "state_not_initialized"}),
            status_code=409,
            mimetype="application/json"
        )

    active = state.get("active_target", "primary")
    primary_url = state["primary_app_url"]
    secondary_url = state["secondary_app_url"]
    target_url = primary_url if active == "primary" else secondary_url

    try:
        r = requests.get(target_url, timeout=5)
        healthy = (r.status_code == 200)
        reason = f"http_{r.status_code}"
    except Exception as e:
        healthy = False
        reason = f"error:{type(e).__name__}"

    state["last_check_utc"] = utc_now_iso()
    state["last_status"] = "HEALTHY" if healthy else "UNHEALTHY"
    state["last_reason"] = reason
    table.upsert_entity(state)

    return func.HttpResponse(
        json.dumps({
            "healthy": healthy,
            "active_target": active,
            "checked_url": target_url,
            "reason": reason
        }),
        status_code=200,
        mimetype="application/json"
    )
