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
  %% =========================
  %% AZURE RESOURCES (MINIMAL)
  %% =========================
  subgraph AZ["Azure (minimal resources)"]
    LA["Logic App (Consumption)\nTrigger: Recurrence (ex: every 1 min)"]
    FA["Function App (Python)"]
    ST["Storage Account"]
    TBL["Table Storage: failover_state\nEntity: PK=failover, RK=state"]
  end

  %% =========================
  %% FUNCTIONS
  %% =========================
  subgraph FN["Azure Functions (HTTP)"]
    HC["Function: health_check (GET)\nauthLevel=function\nURL: /api/health_check?code=KEY_HEALTH"]
    DF["Function: do_failover (POST)\nauthLevel=function\nURL: /api/do_failover?code=KEY_FAILOVER"]
  end

  %% =========================
  %% ORCHESTRATION FLOW
  %% =========================
  LA -->|1) HTTP GET health_check| HC
  HC -->|2) Read + Update state| TBL
  HC -->|3) Check endpoint based on active_target| EP["Active endpoint\n(primary_endpoint or secondary_endpoint)"]
  EP -->|HTTP GET /health| RES["HTTP response / timeout"]
  RES -->|4) last_status,last_reason,last_check_utc| TBL
  HC -->|Return {healthy, reason}| LA

  LA --> DEC{"healthy == false ?"}
  DEC -- "No" --> ENDOK["Stop (no failover)"]
  DEC -- "Yes" -->|5) HTTP POST do_failover| DF

  DF -->|6) Read state| TBL
  DF --> COOLDOWN{"now < lock_until_utc ?"}
  COOLDOWN -- "Yes" --> SKIP["Return: changed=false\nstatus=FAILOVER_SKIPPED (cooldown)"]
  COOLDOWN -- "No" --> SWITCH["7) Toggle active_target\nfailover_count++\nlock_until_utc = now + cooldown\nlast_status=FAILOVER_DONE"]
  SWITCH -->|8) Write state| TBL
  DF --> END["Stop (run finished)"]

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
