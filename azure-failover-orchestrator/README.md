
# Microsoft Cloud Devoteam Tribe Demo — Azure Failover Orchestrator
**Knowledge‑sharing demo** for the Microsoft Cloud Devoteam Tribe

This repository demonstrates a **simple, explainable Azure-native failover pattern**, designed for demos and team knowledge sharing.

It mirrors the classic **AWS Step Functions + Lambda + DynamoDB** pattern using Azure services:

- **Azure Logic App (Consumption)** → Orchestration layer  
- **Azure Functions (Python)** → Execution logic  
- **Azure Table Storage** → Centralized state (single source of truth)

---

## What this demo shows

A **deterministic failover loop**:

1. Periodically check the health of the **active endpoint**
2. If the endpoint is unhealthy → **switch traffic target** (primary ↔ secondary)
3. Store all decisions in **one Table Storage entity**
4. Enforce a **cooldown** to avoid infinite failover loops

This makes the logic:
- Easy to reason about
- Easy to debug
- Easy to explain to a team

---

## Architecture (simplified)

```mermaid
flowchart TD

  LA["Logic App<br/>Timer"]
  HC["health_check<br/>Function"]
  DF["do_failover<br/>Function"]
  TBL["Table Storage<br/>failover_state"]
  EP["Active endpoint<br/>(primary or secondary)"]

  LA --> HC
  HC --> EP
  EP --> HC
  HC --> TBL
  HC --> LA

  LA --> DEC{healthy?}
  DEC -->|yes| END["Stop"]
  DEC -->|no| DF

  DF --> TBL
```

---

## Core components

### Logic App
- Runs on a schedule (for example every 1 minute)
- Calls `health_check`
- Decides whether to call `do_failover`

### health_check (Azure Function)
- Reads current state from Table Storage
- Checks the active endpoint health
- Updates status and timestamp
- Returns `healthy = true | false`

### do_failover (Azure Function)
- Enforces cooldown (`lock_until_utc`)
- Toggles `active_target`
- Increments `failover_count`
- Persists the new state

### Table Storage
- **Table:** `failover_state`
- **One single row only**:
  - PartitionKey = `failover`
  - RowKey = `state`

This table is the **single source of truth**.

---

## End‑to‑end test (step by step)

### 1️⃣ Verify initial state

In **Storage Account → Storage Browser → Tables → failover_state**, confirm:

- `active_target = primary`
- `failover_count = 0`
- `last_status = OK`

---

### 2️⃣ Test `health_check` manually

```bash
curl "https://<function_app>.azurewebsites.net/api/health_check?code=<HEALTH_KEY>"
```

Expected result:
```json
{
  "healthy": true,
  "active_target": "primary"
}
```

Table updates:
- `last_check_utc` updated
- `last_status = OK`

---

### 3️⃣ Force a failure (safe demo method)

Edit the **Table entity**:
- Set `primary_endpoint` to an invalid URL  
  Example:
  ```
  https://127.0.0.1/health
  ```

Wait for the next Logic App run.

---

### 4️⃣ Observe automatic failover

In **Logic App → Runs history**:
- `health_check` runs
- Condition evaluates to **false**
- `do_failover` is executed

In **Table Storage**, verify:
- `active_target = secondary`
- `failover_count = 1`
- `last_status = FAILOVER_DONE`
- `lock_until_utc` is set

---

### 5️⃣ Validate cooldown protection

Immediately call:
```bash
curl -X POST "https://<function_app>.azurewebsites.net/api/do_failover?code=<FAILOVER_KEY>"
```

Expected result:
```json
{
  "changed": false,
  "reason": "cooldown_active"
}
```

No state change should occur.

---

### 6️⃣ Restore normal state

- Fix `primary_endpoint` back to a valid URL
- Wait for cooldown to expire
- System stabilizes automatically

---

## Logging (no Application Insights required)

If Application Insights is not allowed:

- **Function App → Log stream** (live)
- **Function → Code + Test → Logs**
- **Kudu → LogFiles**
  - `/LogFiles/Application/Functions/`

This is sufficient for demos and troubleshooting.

---

## Why this design works well for demos

- Minimal Azure resources
- No hidden magic
- All decisions visible in Table Storage
- Easy AWS → Azure comparison
- Easy to extend later (Key Vault, Managed Identity, alerts)

---

## License

Internal demo for **Devoteam Tribe knowledge sharing**
