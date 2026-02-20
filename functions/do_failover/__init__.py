import os, json, logging, datetime as dt
import requests
import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError

PK = "failover"
RK = "state"

def utc_now():
    return dt.datetime.utcnow().replace(microsecond=0)

def utc_now_iso():
    return utc_now().isoformat() + "Z"

def get_arm_token_sp() -> str:
    tenant = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["AZURE_CLIENT_ID"]
    client_secret = os.environ["AZURE_CLIENT_SECRET"]

    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://management.azure.com/.default",
    }
    r = requests.post(token_url, data=data, timeout=15)
    if r.status_code != 200:
        raise Exception(f"token_failed:{r.status_code}:{r.text}")
    return r.json()["access_token"]

def update_cname(target_hostname: str) -> dict:
    sub = os.environ["SUBSCRIPTION_ID"]
    rg = os.environ["RESOURCE_GROUP_NAME"]
    zone = os.environ["DNS_ZONE_NAME"]
    record = os.environ["DNS_RECORD_NAME"]
    ttl = int(os.environ.get("DNS_TTL", "30"))
    api_version = os.environ.get("ARM_API_VERSION", "2018-05-01")

    # Azure DNS REST: Record Sets - Create Or Update (CNAME) :contentReference[oaicite:9]{index=9}
    url = (
        f"https://management.azure.com/subscriptions/{sub}"
        f"/resourceGroups/{rg}"
        f"/providers/Microsoft.Network/dnsZones/{zone}"
        f"/CNAME/{record}"
        f"?api-version={api_version}"
    )

    body = {
        "properties": {
            "TTL": ttl,
            "CNAMERecord": {
                "cname": target_hostname
            }
        }
    }

    token = get_arm_token_sp()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    r = requests.put(url, headers=headers, json=body, timeout=30)
    if r.status_code not in (200, 201):
        raise Exception(f"dns_update_failed:{r.status_code}:{r.text}")

    return {"status_code": r.status_code, "target": target_hostname}

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("do_failover: start")

    cooldown = int(os.environ.get("COOLDOWN_MINUTES", "5"))

    table = TableServiceClient.from_connection_string(
        os.environ["AzureWebJobsStorage"]
    ).get_table_client(os.environ["STATE_TABLE_NAME"])

    try:
        state = table.get_entity(PK, RK)
    except ResourceNotFoundError:
        return func.HttpResponse(
            json.dumps({"changed": False, "status": "STATE_NOT_INITIALIZED"}),
            status_code=409,
            mimetype="application/json"
        )

    now = utc_now()
    lock_until_raw = (state.get("lock_until_utc") or "").strip()
    if lock_until_raw:
        lock_until = dt.datetime.fromisoformat(lock_until_raw.replace("Z", ""))
        if now < lock_until:
            return func.HttpResponse(
                json.dumps({"changed": False, "status": "COOLDOWN", "lock_until_utc": lock_until_raw}),
                status_code=200,
                mimetype="application/json"
            )

    current = state.get("active_target", "primary")
    new_target = "secondary" if current == "primary" else "primary"

    # On bascule le DNS vers l'autre WebApp
    if new_target == "primary":
        target_hostname = os.environ["PRIMARY_APP_URL"].replace("https://", "")
    else:
        target_hostname = os.environ["SECONDARY_APP_URL"].replace("https://", "")

    try:
        dns_result = update_cname(target_hostname)
        ok = True
        reason = "dns_cname_updated"
    except Exception as e:
        ok = False
        reason = f"failover_error:{type(e).__name__}"
        logging.error(str(e))

    if not ok:
        return func.HttpResponse(
            json.dumps({"changed": False, "status": "FAILOVER_ERROR", "reason": reason}),
            status_code=500,
            mimetype="application/json"
        )

    state["active_target"] = new_target
    state["failover_count"] = int(state.get("failover_count", 0)) + 1
    state["last_status"] = "FAILOVER_DONE"
    state["last_reason"] = reason
    state["last_check_utc"] = utc_now_iso()
    state["lock_until_utc"] = (now + dt.timedelta(minutes=cooldown)).isoformat() + "Z"
    table.upsert_entity(state)

    return func.HttpResponse(
        json.dumps({
            "changed": True,
            "status": "FAILOVER_DONE",
            "new_active_target": new_target,
            "dns": dns_result,
            "lock_until_utc": state["lock_until_utc"]
        }),
        status_code=200,
        mimetype="application/json"
    )
