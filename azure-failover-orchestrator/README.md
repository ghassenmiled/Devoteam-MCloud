
# Microsoft Cloud Devoteam Tribe Demo — Azure Failover Orchestrator
**Knowledge-sharing demo** for the Microsoft Cloud Devoteam Tribe

This repository is a **demo** to share an Azure-native pattern similar to:
**AWS Step Functions + Lambda + DynamoDB**, but implemented with:
- **Azure Logic App (Consumption)** → Orchestrator (Step Functions equivalent)
- **Azure Functions (Python)** → Compute actions (Lambda equivalent)
- **Azure Table Storage** → State store (DynamoDB equivalent)

The demo implements a **deterministic failover loop**:
1) Check active endpoint health  
2) If unhealthy, toggle active target (primary ↔ secondary) with a cooldown lock  
3) Persist state in a single Table Storage entity  

> ⚠️ Demo scope  
> Minimal resources, clear logic, easy to explain.  
> Not intended as-is for regulated production without extra hardening.

---

## Architecture

```mermaid
flowchart TD

  subgraph Azure["Azure resources (demo)"]
    LA["Logic App<br/>Recurrence trigger"]
    FA["Function App<br/>Python"]
    ST["Storage Account"]
    TBL["Table Storage<br/>failover_state"]
  end

  subgraph Functions["Azure Functions"]
    HC["health_check<br/>GET"]
    DF["do_failover<br/>POST"]
  end

  ST --> TBL
  FA --> HC
  FA --> DF

  LA --> HC
  HC --> TBL
  HC --> EP["Active endpoint<br/>primary or secondary"]
  EP --> RES["HTTP response"]
  RES --> TBL
  HC --> LA

  LA --> DEC{healthy false}
  DEC -->|no| ENDOK["Stop"]
  DEC -->|yes| DF

  DF --> TBL
  DF --> COOLDOWN{cooldown active}
  COOLDOWN -->|yes| SKIP["Skip failover"]
  COOLDOWN -->|no| SWITCH["Toggle target<br/>Increment counter"]
  SWITCH --> TBL
```

---

## Repo structure

```
azure-failover-orchestrator/
├── README.md
├── infra/                      # Terraform (Azure resources)
├── functions/                  # Azure Functions (Python)
└── scripts/
```

---

## State model (Table Storage)

**Table:** `failover_state`  
**Single entity only**

| Field | Description |
|---|---|
| active_target | `primary` or `secondary` |
| primary_endpoint | Health URL of primary |
| secondary_endpoint | Health URL of secondary |
| last_status | OK / ERROR / FAILOVER_DONE |
| last_reason | Text reason |
| last_check_utc | ISO timestamp |
| failover_count | Number of failovers |
| lock_until_utc | Cooldown timestamp |

---

## License
Internal demo for Devoteam Tribe knowledge sharing.
