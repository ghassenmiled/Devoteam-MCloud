#!/usr/bin/env bash
set -euo pipefail

RG="${1:-}"
SA="${2:-}"
PRIMARY="${3:-}"
SECONDARY="${4:-}"

if [[ -z "$RG" || -z "$SA" || -z "$PRIMARY" || -z "$SECONDARY" ]]; then
  echo "Usage: $0 <RESOURCE_GROUP> <STORAGE_ACCOUNT_NAME> <PRIMARY_ENDPOINT> <SECONDARY_ENDPOINT>"
  exit 1
fi

TABLE="failoverstate"

CONN_STR=$(az storage account show-connection-string   --name "$SA"   --resource-group "$RG"   --query connectionString -o tsv)

az storage entity insert   --connection-string "$CONN_STR"   --table-name "$TABLE"   --entity     PartitionKey="failover"     RowKey="state"     active_target="primary"     primary_endpoint="$PRIMARY"     secondary_endpoint="$SECONDARY"     last_status="OK"     last_reason="init"     last_check_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"     failover_count=0     lock_until_utc=""

echo "Inserted entity failover/state into table ${TABLE}"
