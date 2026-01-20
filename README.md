# Devoteam-MCloud

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
  %% STATE FIELDS
  %% =========================
  subgraph STATE["State schema stored in Table entity failover/state"]
    S1["active_target: primary | secondary"]
    S2["primary_endpoint: URL"]
    S3["secondary_endpoint: URL"]
    S4["last_status: OK | FAILOVER_DONE | ERROR"]
    S5["last_reason: string"]
    S6["last_check_utc: ISO string"]
    S7["failover_count: int"]
    S8["lock_until_utc: ISO string"]
  end

  %% Wiring
  ST --> TBL
  FA --> HC
  FA --> DF
  TBL --- STATE

  %% =========================
  %% ORCHESTRATION FLOW
  %% =========================
  LA -->|1) HTTP GET health_check| HC
  HC -->|2) Read state| TBL
  HC -->|3) Check endpoint based on active_target| EP["Active endpoint\n(primary_endpoint or secondary_endpoint)"]
  EP -->|HTTP GET /health| RES["HTTP response / timeout"]
  RES -->|4) Update state:\nlast_status,last_reason,last_check_utc| TBL
  HC -->|Return JSON:\n{healthy, active_target, reason}| LA

  LA --> DEC{"healthy == false ?"}
  DEC -- "No (healthy true)" --> ENDOK["Stop (no failover)"]
  DEC -- "Yes (unhealthy)" -->|5) HTTP POST do_failover| DF

  DF -->|6) Read state| TBL
  DF --> COOLDOWN{"now < lock_until_utc ?"}
  COOLDOWN -- "Yes" --> SKIP["Return: changed=false\nstatus=FAILOVER_SKIPPED"]
  SKIP --> LA2["Logic App ends"]

  COOLDOWN -- "No" --> SWITCH["7) Toggle active_target\nprimary <-> secondary\nfailover_count++\nlock_until_utc = now + cooldown\nlast_status=FAILOVER_DONE"]
  SWITCH -->|8) Write state| TBL
  DF -->|Return JSON:\n{changed:true,new_active_target,...}| LA2
  LA2 --> END["Stop (run finished)"]
