import os
import json
import datetime as dt
import logging
import azure.functions as func
from azure.data.tables import TableServiceClient

PK = "failover"
RK = "state"

def utc_now():
    return dt.datetime.utcnow().replace(microsecond=0)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("do_failover: start")

    cooldown_minutes = int(os.environ.get("COOLDOWN_MINUTES", "10"))

    table = TableServiceClient.from_connection_string(
        os.environ["AzureWebJobsStorage"]
    ).get_table_client(os.environ["STATE_TABLE_NAME"])

    state = table.get_entity(PK, RK)

    now = utc_now()
    lock_until_raw = state.get("lock_until_utc", "")

    if lock_until_raw:
        lock_until = dt.datetime.fromisoformat(lock_until_raw.replace("Z", ""))
        if now < lock_until:
            logging.warning("do_failover: cooldown_active until=%s", lock_until_raw)
            return func.HttpResponse(
                json.dumps({
                    "changed": False,
                    "status": "FAILOVER_SKIPPED",
                    "reason": "cooldown_active",
                    "lock_until_utc": lock_until_raw
                }),
                status_code=200,
                mimetype="application/json"
            )

    current = state.get("active_target", "primary")
    new_target = "secondary" if current == "primary" else "primary"

    state["active_target"] = new_target
    state["failover_count"] = int(state.get("failover_count", 0)) + 1
    state["last_status"] = "FAILOVER_DONE"
    state["last_reason"] = f"switched_from_{current}_to_{new_target}"
    state["last_check_utc"] = now.isoformat() + "Z"
    state["lock_until_utc"] = (now + dt.timedelta(minutes=cooldown_minutes)).isoformat() + "Z"

    table.upsert_entity(state)

    logging.info("do_failover: switched %s -> %s count=%s", current, new_target, state["failover_count"])

    return func.HttpResponse(
        json.dumps({
            "changed": True,
            "status": "FAILOVER_DONE",
            "new_active_target": new_target,
            "failover_count": state["failover_count"],
            "lock_until_utc": state["lock_until_utc"]
        }),
        status_code=200,
        mimetype="application/json"
    )
