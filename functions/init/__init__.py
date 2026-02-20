import os, json, logging
import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError

PK = "failover"
RK = "state"

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("init: start")

    table = TableServiceClient.from_connection_string(
        os.environ["AzureWebJobsStorage"]
    ).get_table_client(os.environ["STATE_TABLE_NAME"])

    entity = {
        "PartitionKey": PK,
        "RowKey": RK,
        "active_target": "primary",
        "failover_count": 0,
        "lock_until_utc": "",
        "primary_app_url": os.environ["PRIMARY_APP_URL"],
        "secondary_app_url": os.environ["SECONDARY_APP_URL"],
    }

    try:
        table.create_entity(entity)
        status = "INIT_CREATED"
    except ResourceExistsError:
        status = "INIT_ALREADY_EXISTS"

    return func.HttpResponse(
        json.dumps({"status": status, "active_target": entity["active_target"]}),
        status_code=200,
        mimetype="application/json"
    )
