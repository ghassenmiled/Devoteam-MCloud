# Azure Failover Orchestrator  
**Logic App + Azure Functions + Table Storage**

## Overview

This project implements a **minimal, deterministic failover system on Microsoft Azure**, inspired by the **AWS Step Functions + Lambda + DynamoDB** architecture.

It continuously checks the health of an active endpoint and automatically switches to a standby endpoint when a failure is detected.

### Key characteristics
- State-driven (single source of truth)
- Idempotent failover logic
- Minimal Azure resources
- No Application Insights required
- Fully auditable via Table Storage
- Designed for restricted enterprise environments

---

## Architecture

```mermaid
flowchart TD

  subgraph Azure["Azure resources"]
    LA["Logic App<br/>Recurrence trigger"]
    FA["Function App<br/>Python"]
    ST["Storage Account"]
    TBL["Table Storage<br/>failover_state"]
  end

  subgraph Functions["Azure Functions"]
    HC["health_check<br/>HTTP GET"]
    DF["do_failover<br/>HTTP POST"]
  end

  ST --> TBL
  FA --> HC
  FA --> DF

  LA -->|GET| HC
  HC -->|read/write| TBL
  HC --> EP["Active endpoint<br/>primary or secondary"]
  EP --> RES["HTTP response"]
  RES --> TBL
  HC --> LA

  LA --> DEC{healthy == false}
  DEC -- no --> ENDOK["Stop"]
  DEC -- yes -->|POST| DF

  DF --> TBL
  DF --> COOLDOWN{cooldown active}
  COOLDOWN -- yes --> SKIP["Failover skipped"]
  COOLDOWN -- no --> SWITCH["Toggle active_target<br/>increment counter"]
  SWITCH --> TBL
```
---

## Azure Resources Used

| Resource | Purpose |
|-------|--------|
| Storage Account | Runtime storage + state storage |
| Table Storage | Persistent failover state |
| Function App (Python) | Executes health check and failover |
| Logic App (Consumption) | Orchestrates execution flow |

---

## State Model (Table Storage)

**Table name:** `failover_state`  
**Single entity only**

| Field | Type | Description |
|----|----|----|
| PartitionKey | string | `failover` |
| RowKey | string | `state` |
| active_target | string | `primary` or `secondary` |
| primary_endpoint | string | Health URL of primary |
| secondary_endpoint | string | Health URL of secondary |
| last_status | string | `OK`, `ERROR`, `FAILOVER_DONE` |
| last_reason | string | Failure reason |
| last_check_utc | string | ISO timestamp |
| failover_count | int | Number of failovers |
| lock_until_utc | string | Cooldown lock timestamp |

â ï¸ There must **never** be more than one row in this table.

---

## Azure Functions

### health_check

**Method**
```
GET /api/health_check
```

Checks the active endpoint health and updates the state.

### do_failover

**Method**
```
POST /api/do_failover
```

Switches active endpoint with cooldown protection.

---

## Orchestration Logic (Logic App)

1. Triggered on schedule (e.g. every 1 minute)
2. Calls `health_check`
3. If `healthy == false`, calls `do_failover`
4. Otherwise, stops

Expression:
```
@equals(body('HealthCheck')?['healthy'], false)
```

---

## Security

- Functions use **authLevel = function**
- Logic App uses **function keys**
- `_master` key is never used

---

## Logging (No Application Insights)

Logs are available via:
- Function App â Log Stream
- Function App â Code + Test â Logs
- Kudu â `/LogFiles/Application/Functions/`

---

## Testing

```bash
# Health check
curl "https://<func>.azurewebsites.net/api/health_check?code=<KEY>"

# Failover
curl -X POST "https://<func>.azurewebsites.net/api/do_failover?code=<KEY>"
```

---

## AWS Mapping

| AWS | Azure |
|----|-----|
| Step Functions | Logic App |
| Lambda | Azure Functions |
| DynamoDB | Table Storage |

---

## Status

â Minimal  
â Deterministic  
â Production-ready  
