# Microsoft Cloud Devoteam Tribe Demo — Azure Failover Orchestrator
**Knowledge-sharing demo** for the Microsoft Cloud Devoteam Tribe

This repository is a **demo** to share an Azure-native pattern similar to:
**AWS Step Functions + Lambda + DynamoDB**, but implemented with:
- **Azure Logic App (Consumption)** → Orchestrator (Step Functions equivalent)
- **Azure Functions (Python)** → Compute actions (Lambda equivalent)
- **Azure Table Storage** → State store (DynamoDB equivalent)

The demo implements a **deterministic failover loop**:
1) check active endpoint health
2) if unhealthy → toggle active target (primary ↔ secondary) with a cooldown lock
3) persist state in a single Table Storage entity

> ⚠️ Demo scope:
> - Minimal resources, clear logic, easy to explain.
> - Not intended as-is for regulated production without additional hardening (network isolation, RBAC, secret mgmt, monitoring, etc.).

---

## Architecture

```mermaid
flowchart TD
  subgraph Azure["Azure resources (demo)"]
    LA["Logic App (Consumption)<br/>Recurrence trigger"]
    FA["Function App (Python)"]
    ST["Storage Account"]
    TBL["Table Storage<br/>failover_state (single entity)"]
  end

  subgraph Functions["Azure Functions (HTTP)"]
    HC["health_check<br/>GET (authLevel=function)"]
    DF["do_failover<br/>POST (authLevel=function)"]
  end

  ST --> TBL
  FA --> HC
  FA --> DF

  LA -->|GET| HC
  HC -->|read/write| TBL
  HC --> EP["Active endpoint<br/>primary or secondary"]
  EP --> RES["HTTP response / timeout"]
  RES --> TBL
  HC --> LA

  LA --> DEC{healthy == false}
  DEC -- no --> ENDOK["Stop"]
  DEC -- yes -->|POST| DF

  DF -->|read/write| TBL
  DF --> COOLDOWN{cooldown active}
  COOLDOWN -- yes --> SKIP["Skip (changed=false)"]
  COOLDOWN -- no --> SWITCH["Toggle active_target<br/>failover_count++<br/>lock_until_utc = now + cooldown"]
  SWITCH --> TBL
```

---

## Repo structure

```
azure-failover-orchestrator/
├── README.md
├── infra/                      # Terraform (Azure resources)
│   ├── versions.tf
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── logicapp.json.tftpl     # Logic App workflow definition template
│   └── terraform.tfvars.example
├── functions/                  # Azure Functions (Python)
│   ├── host.json
│   ├── requirements.txt
│   ├── health_check/
│   │   ├── function.json
│   │   └── __init__.py
│   └── do_failover/
│       ├── function.json
│       └── __init__.py
└── scripts/
    ├── package_functions.sh    # Create functions.zip
    └── init_state_entity.sh    # Create the single Table entity (via az cli)
```

---

## State model (Table Storage)

**Table:** `failover_state`  
**Single entity (only one row):**
- `PartitionKey = "failover"`
- `RowKey = "state"`

| Field | Type | Description |
|---|---|---|
| active_target | string | `primary` or `secondary` |
| primary_endpoint | string | Health URL of primary |
| secondary_endpoint | string | Health URL of secondary |
| last_status | string | `OK`, `ERROR`, `FAILOVER_DONE` |
| last_reason | string | Text reason |
| last_check_utc | string | ISO timestamp |
| failover_count | int | Number of failovers |
| lock_until_utc | string | ISO timestamp (cooldown) |

---

## Prerequisites

### Local workstation
- Terraform **>= 1.5**
- Azure CLI (`az`)
- zip utility (Linux/macOS) or PowerShell `Compress-Archive` (Windows)

### Azure permissions
Minimum permissions (demo):
- Create Resource Group
- Create Storage Account + Table
- Create Function App + deploy zip
- Create Logic App
- Read Function keys (or set authLevel to anonymous for purely local demo, not recommended)

If you **cannot create Application Insights**:
- It's OK. This demo uses portal **Log stream** + **Kudu logs** (see Logging section).

---

## How to run (end-to-end)

### 0) Clone
```bash
git clone <your-repo-url>
cd azure-failover-orchestrator
```

### 1) Azure credentials

#### Option A — Interactive login (recommended for demo)
```bash
az login
az account set --subscription "<SUBSCRIPTION_ID_OR_NAME>"
```

#### Option B — Service Principal (CI / non-interactive)
```bash
az login --service-principal   -u "<APP_ID>" -p "<CLIENT_SECRET>" --tenant "<TENANT_ID>"
az account set --subscription "<SUBSCRIPTION_ID_OR_NAME>"
```

> Tip: You can verify:
```bash
az account show -o table
```

---

### 2) Package Functions code → `functions.zip`

Linux/macOS:
```bash
./scripts/package_functions.sh
```

Windows PowerShell (from repo root):
```powershell
Compress-Archive -Path .\functions\* -DestinationPath .\functions.zip -Force
```

You should now have:
- `functions.zip` at repo root

---

### 3) Configure Terraform variables

Copy example tfvars:
```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

Edit `infra/terraform.tfvars` and fill:
- `resource_group_name`
- `location`
- `storage_account_name` (must be globally unique, lowercase, 3-24 chars)
- `function_app_name`
- `primary_endpoint`
- `secondary_endpoint`
- `health_function_key` and `failover_function_key` (see next step)
- `functions_zip_path` (default points to `../functions.zip`)

---

### 4) Deploy infrastructure (Terraform)

```bash
cd infra
terraform init
terraform apply
```

Terraform creates:
- Resource Group
- Storage Account + Table `failover_state`
- Function App (zip deploy from `../functions.zip`)
- Logic App (workflow calling the functions)

---

### 5) Get Function keys (required if authLevel=function)

In Azure Portal:
- Function App → Functions → `health_check` → **Function keys**
- Copy the `default` **function key**
- Same for `do_failover`

Put them into `infra/terraform.tfvars`:
- `health_function_key = "..."`
- `failover_function_key = "..."`

Then re-apply:
```bash
cd infra
terraform apply
```

> Note: In this demo, keys are injected into the Logic App definition. Terraform state may contain them.
> For real production, use Key Vault + Managed Identity patterns instead.

---

### 6) Create the single Table entity (state row)

Terraform creates the **table**, but not the **entity** (row). Do this once.

#### Option A — Azure Portal (Storage Browser)
Storage Account → **Storage browser** → Tables → `failover_state` → **Add entity**
- PartitionKey: `failover`
- RowKey: `state`
- Add properties:
  - active_target (String) = primary
  - primary_endpoint (String) = your primary endpoint
  - secondary_endpoint (String) = your secondary endpoint
  - last_status (String) = OK
  - last_reason (String) = init
  - last_check_utc (String) = 2026-01-01T00:00:00Z
  - failover_count (Int32) = 0
  - lock_until_utc (String) = ""

#### Option B — Azure CLI script
From repo root:
```bash
./scripts/init_state_entity.sh   "<RESOURCE_GROUP>" "<STORAGE_ACCOUNT_NAME>"   "<PRIMARY_ENDPOINT>" "<SECONDARY_ENDPOINT>"
```

---

### 7) Test the Functions manually

Get base URL from Terraform outputs or Azure Portal:
- `https://<function_app>.azurewebsites.net/api`

```bash
# health_check (GET)
curl "https://<function_app>.azurewebsites.net/api/health_check?code=<HEALTH_KEY>"

# do_failover (POST)
curl -X POST "https://<function_app>.azurewebsites.net/api/do_failover?code=<FAILOVER_KEY>"
```

Check Table entity values:
- `active_target` toggles
- `failover_count` increments
- `lock_until_utc` set (cooldown)

---

### 8) Validate orchestrator (Logic App)

Azure Portal:
- Logic App → **Runs history**
- Every interval it calls:
  - `health_check`
  - and if unhealthy: `do_failover`

To simulate a failure quickly:
- Temporarily set `primary_endpoint` in the Table entity to an invalid URL
- Wait for the next Logic App run
- Observe failover to `secondary`
- Restore the correct URL

---

## Logging (no Application Insights)

If you don’t have rights for Application Insights, use:

1) **Function App → Log stream** (live logs)
2) Function → **Code + Test → Logs** (for manual runs)
3) **Kudu**: Function App → Advanced Tools → Go → LogFiles  
   - `/LogFiles/Application/Functions/Function/health_check/`
   - `/LogFiles/Application/Functions/Function/do_failover/`
   - `/LogFiles/Application/Functions/Host/`

---

## Security notes (demo vs prod)

Demo uses **function keys** to keep things simple.
- Use **Function keys** (least privilege) rather than Host keys.
- Never use `_master`.

For production hardening (future):
- Managed Identity + Key Vault (no keys in Logic App)
- Private endpoints / VNET integration
- RBAC-only Storage access
- Monitoring + alerting + runbooks

---

## Troubleshooting

### Mermaid diagram not rendering on GitHub
- Ensure the block is exactly:
  - ```mermaid
  - (diagram)
  - ```

### `ModuleNotFoundError` in Functions
- Verify `functions/requirements.txt`
- Restart Function App after deployment

### `Table entity not found`
- Ensure you created the single entity:
  - PK `failover` / RK `state`

---

## License
Internal demo for Devoteam Tribe knowledge sharing.
