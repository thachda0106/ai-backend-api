# Deep Dive — `terraform/` AWS Infrastructure (ai-backend-api)

Target: `terraform/` — Terraform IaC that provisions the full AWS stack for the FastAPI backend.
Audience: someone who has never read these files.
All line references are to files under `terraform/` unless prefixed (`app/...`, `Dockerfile`).

---

## 1. Overview Table

| Name | Path | Role |
|---|---|---|
| Root versions file | `terraform/versions.tf` | Pin block (Terraform ≥1.7, AWS ~>5.0); sits outside every root module — effectively decorative |
| Bootstrap | `terraform/bootstrap/main.tf` | One-time run: creates the S3 bucket that stores all Terraform state |
| Dev root module | `terraform/environments/dev/main.tf` | Wires all 6 child modules; state key `dev/terraform.tfstate` |
| Staging root module | `terraform/environments/staging/main.tf` | Same wiring as dev; state key `staging/terraform.tfstate` |
| Production root module | `terraform/environments/production/main.tf` | Same wiring + hardened overrides (IMMUTABLE tags, 7-day snapshots, tighter alarms) |
| Env variable schemas | `terraform/environments/*/variables.tf` | Declares the 15 root variables fed from `terraform.tfvars` |
| Env tfvars | `terraform/environments/*/terraform.tfvars` | Per-env values (not read here — permission-blocked) |
| Network module | `terraform/modules/network/*` | VPC, subnets, IGW, NAT, route tables, 5 security groups |
| Registry module | `terraform/modules/registry/*` | ECR repository + image retention lifecycle policy |
| Compute module | `terraform/modules/compute/*` | ECS cluster, ALB + listeners, API task def/service, IAM roles, autoscaling |
| Redis module | `terraform/modules/redis/*` | ElastiCache replication group + subnet group |
| Qdrant module | `terraform/modules/qdrant/*` | EFS filesystem, Qdrant ECS task def/service on Fargate |
| Observability module | `terraform/modules/observability/*` | SNS alarm topic + 3 CloudWatch alarms |
| App runtime (consumer) | `app/main.py`, `app/core/config/settings.py`, `Dockerfile` | The image this infrastructure deploys and connects to |

---

## 2. Declarative Knowledge

### 2.1 The Problem

ECS Fargate tasks get their own ENI and live in **private** subnets with no public IP.
Without the machinery below, three things are impossible at once:

```
                         ┌── the problem ─────────────────────────────────┐
   internet              │                                                │
      │                  │  1. No route IN:  private tasks have no IP     │
      ▼                  │     reachable from the internet.               │
  [ ALB :443 ] ──────────┼─►  ALB is the ONLY door (public subnets).      │
      │ :8000            │                                                │
      ▼                  │  2. No route OUT: tasks must reach ECR/SSM/    │
  [ API task :8000 ]     │     OpenAI via the NAT Gateway.                │
      │                  │                                                │
      ├─ 6379 ─► Redis   │  3. No trust: any VPC resource could talk to   │
      ├─ 6333 ─► Qdrant  │     Redis/Qdrant. SG-id chaining fixes this.   │
      └─ 2049 ─► EFS     └────────────────────────────────────────────────┘
```

The whole design is: **one public door (ALB), one private neighborhood (private subnets),
and a chain of security groups where each door only accepts traffic from the previous door.**

### 2.2 Core Variables

| Variable | Type | Plain-English meaning |
|---|---|---|
| `project` | string | Name prefix stamped on every resource, e.g. `ai-backend-api` |
| `environment` | string | Which copy of the stack: `dev`, `staging`, or `production` |
| `aws_region` | string | AWS region everything is created in, e.g. `us-east-1` |
| `aws_account_id` | string | Your AWS account number, used to build ARNs for SSM/secrets access |
| `azs` | list(string) | Which physical data-center zones to spread across, e.g. `["us-east-1a","us-east-1b"]` |
| `certificate_arn` | string | Pointer to the TLS certificate the ALB uses for HTTPS |
| `image_tag` | string | Which Docker image tag the API runs, default `latest` (e.g. `v1.2.3`) |
| `env_vars` | map(string) | Plain environment variables handed to the API container (currently never filled — see §7.2) |
| `auth_token` | string (sensitive) | Redis password; empty means "no AUTH token" |
| `qdrant_api_key` | string (sensitive) | Optional password for Qdrant; empty means "open access" |
| `api_cpu` / `api_memory` | number | API task size in CPU units / MiB (512 = ½ vCPU, 1024 = 1 GiB) |
| `api_desired_count` / `min_count` / `max_count` | number | How many API tasks to run now / floor / ceiling for autoscaling |
| `redis_node_type` | string | Redis machine size, e.g. `cache.t3.micro` |
| `redis_num_clusters` | number | 1 = single Redis node (dev); 2 = primary + replica (HA) |
| `redis_automatic_failover` / `multi_az` | bool | Promote replica on failure / keep the pair in different zones |
| `snapshot_retention` | number | Days Redis snapshots are kept (1 default, 7 in production) |
| `qdrant_desired_count` / `cpu` / `memory` | number | How many Qdrant tasks and their size (1024 CPU = 1 vCPU) |
| `image_tag_mutability` | string | `MUTABLE` lets you overwrite a tag; `IMMUTABLE` (production) forbids it |
| `lifecycle_policy_count` | number | How many tagged ECR images to keep before deleting old ones |
| `alarm_email` | string | Email subscribed to alarms; empty string means "create no subscription" |
| `cpu_threshold` / `memory_threshold` | number | % utilization that trips the CPU/memory alarms (80 default, 70 production) |
| `error_5xx_threshold` | number | Server-error count per minute that trips the 5xx alarm (5 default, 1 production) |

### 2.3 Key Concepts

| Term | Definition |
|---|---|
| Root module | A directory you run `terraform apply` in; here: one per environment |
| Child module | A reusable folder under `modules/` that a root module calls with inputs |
| Remote state | Terraform's memory of what it created, stored in the bootstrap S3 bucket |
| Lockfile locking | S3-native lock (`use_lockfile = true`) — stops two applies running at once, no DynamoDB needed |
| Fargate | AWS runs the containers for you; you never see or manage servers |
| `awsvpc` network mode | Each task gets its own network card (ENI) with a private-subnet IP |
| Execution role | IAM identity the **ECS agent** uses: pull image from ECR, write logs |
| Task role | IAM identity the **application** uses: read SSM parameters / secrets |
| Target-group health check | ALB-level probe: `GET /health` must return HTTP 200 |
| Container health check | Inside-the-container probe: hits `localhost:8000/health` |
| Transit encryption | Forces TLS on connections (Redis: client must use `rediss://`) |
| EFS mount target | Per-subnet network plug that lets containers mount a shared disk (NFS, port 2049) |
| Target-tracking autoscaling | "Keep average CPU at X%"; AWS adds/removes tasks automatically |
| ECR lifecycle policy | Rules that auto-delete old Docker images |
| Evaluation period | How many consecutive 60-second samples must breach before an alarm fires |

---

## 3. Data Structures

### 3.1 Remote-state backend (`environments/dev/main.tf:9-16`, identical shape in all envs)

```hcl
type BackendS3 = {
  bucket       = "REPLACE_WITH_BOOTSTRAP_OUTPUT"  # paste bootstrap's state_bucket_name output
  key          = "dev/terraform.tfstate"          # one state file per environment = total isolation
  region       = "us-east-1"
  encrypt      = true                             # AES256 server-side encryption
  use_lockfile = true                             # S3-native lock; no DynamoDB table
}
```

### 3.2 Root variable schema (`environments/*/variables.tf:1-31`)

```hcl
type EnvConfig = {
  project:        string        # resource name prefix
  environment:    string        # dev | staging | production
  aws_region:     string
  aws_account_id: string
  azs:            list(string)  # one subnet pair per AZ
  certificate_arn: string       # TLS cert for ALB :443 listener
  image_tag:      string = "latest"   # which ECR image to deploy
  alarm_email:    string = ""         # "" ⇒ no SNS email subscription
  redis_node_type: string; redis_num_clusters: number
  redis_automatic_failover: bool; redis_multi_az: bool
  api_cpu: number; api_memory: number
  api_desired_count: number; api_min_count: number; api_max_count: number
  qdrant_desired_count: number; qdrant_cpu: number; qdrant_memory: number
}
```

### 3.3 Network module output contract (`modules/network/outputs.tf:1-39`)

```hcl
type NetworkOutputs = {
  vpc_id:             string        # e.g. vpc-0abc...
  public_subnet_ids:  list(string)  # for the ALB only
  private_subnet_ids: list(string)  # for API, Redis, Qdrant, EFS
  alb_sg_id:    string  # SG accepting 80/443 from 0.0.0.0/0
  api_sg_id:    string  # SG accepting 8000 from ALB SG only
  redis_sg_id:  string  # SG accepting 6379 from API SG only
  qdrant_sg_id: string  # SG accepting 6333+6334 from API SG only
  efs_sg_id:    string  # SG accepting 2049 from API SG + Qdrant SG
}
```

### 3.4 API container definition (`modules/compute/main.tf:169-200`)

```hcl
type ApiContainer = {
  name:      "api"
  image:     "<ecr_url>:<image_tag>"          # e.g. .../ai-backend-api-dev-api:v1.2.3
  essential: true                             # container dies → task dies
  portMappings: [ { containerPort = 8000 } ]  # matches api SG + target group
  environment: [ { name, value } for (k,v) in env_vars ]  # currently always empty (§7.2)
  logConfiguration: { awslogs-group = "/ecs/<proj>-<env>/api", retention 30d }
  healthCheck: {
    command: 'python urllib → http://localhost:8000/health'
    interval 30s, timeout 10s, retries 3, startPeriod 20s
  }
}
```

### 3.5 Qdrant container definition (`modules/qdrant/main.tf:35-95`)

```hcl
type QdrantContainer = {
  image: "qdrant/qdrant:v1.14.0"              # pinned; upgrades are deliberate
  portMappings: [ 6333 (REST), 6334 (gRPC) ]
  mountPoints: [ /qdrant/storage ← EFS volume "qdrant-storage", read-write ]
  environment: [
    QDRANT__STORAGE__STORAGE_PATH    = "/qdrant/storage"
    QDRANT__STORAGE__SNAPSHOTS_PATH  = "/qdrant/storage/snapshots"
    QDRANT__SERVICE__GRPC_PORT       = "6334"
    QDRANT__LOG_LEVEL                = "INFO"
    QDRANT__SERVICE__API_KEY         = <only if qdrant_api_key != "">
  ]                                             # double __ = nested YAML keys in Qdrant
  volume: efs_volume_configuration { transit_encryption = "ENABLED" }
}
```

### 3.6 Redis replication group (`modules/redis/main.tf:12-44`)

```hcl
type RedisGroup = {
  port: 6379
  num_cache_clusters: 1 (dev) | 2 (HA)     # 2 enables primary + replica
  automatic_failover_enabled: false (dev) | true (HA)   # requires ≥2 nodes
  multi_az_enabled: false (dev) | true (HA)
  at_rest_encryption_enabled: true
  transit_encryption_enabled: true          # forces TLS clients (rediss://)
  auth_token: <var if non-empty, else null> # set via TF_VAR_auth_token in CI
  snapshot_retention_limit: 1 day (default) | 7 days (production)
  snapshot_window: "03:00-05:00", maintenance_window: "sun:05:00-sun:07:00"
}
```

### 3.7 ECR lifecycle policy (`modules/registry/main.tf:19-44`)

```hcl
type LifecyclePolicy = {
  rule1: { priority 1, untagged images older than 1 day → expire }
  rule2: { priority 2, tagged images with prefix "v", more than
           lifecycle_policy_count kept → expire oldest beyond N }
}
```

### 3.8 Autoscaling policy (`modules/compute/main.tf:245-267`)

```hcl
type TargetTrackingConfig = {
  scalable_dimension: "ecs:service:DesiredCount"  # scales task COUNT, not size
  min_capacity: api_min_count                     # floor (e.g. 1)
  max_capacity: api_max_count                     # ceiling (e.g. 4)
  predefined_metric: "ECSServiceAverageCPUUtilization"
  target_value: 70.0                              # desired average CPU %
  scale_out_cooldown: 60s                         # may add tasks again after 60s
  scale_in_cooldown: 300s                         # waits 5 min before shrinking
}
```

---

## 4. Algorithm Diagrams

### 4.1 Resource naming formula

```
input:  project = "ai-backend-api",  environment = "dev"
formula: "${project}-${environment}-<role>"
output: cluster = "ai-backend-api-dev"
        log group = "/ecs/ai-backend-api-dev/api"
        SNS topic = "ai-backend-api-dev-alarms"
        state path = "s3://ai-backend-api-tfstate-123456789012/dev/terraform.tfstate"
```
Every resource in every module derives its name this way — rename via `project`/`environment` only.

### 4.2 network — topology + trust chain

```
VPC 10.0.0.0/16
 ├─ public  10.0.1.0/24 (AZ a) ──┬─ route 0.0.0.0/0 → IGW      (network/main.tf:83-96)
 ├─ public  10.0.2.0/24 (AZ b)   └─ hosts ALB + NAT GW (public[0], :69-80)
 ├─ private 10.0.10.0/24 (AZ a) ─┬─ route 0.0.0.0/0 → NAT GW   (:104-117)
 ├─ private 10.0.11.0/24 (AZ b)  ┘
 └─ SG chain (ingress references previous SG id, never CIDRs):
    internet ─80/443→ ALB ─8000→ API ─6379→ Redis
                                  ├─6333/6334→ Qdrant
                                  └─2049────→ EFS ◄─2049─ Qdrant
```
`input → formula → output`: `azs=["us-east-1a","us-east-1b"]` → `count = length(azs)` → 2 public + 2 private subnets (network/main.tf:15-45).

### 4.3 compute — deploy gate chain

```
image_tag=v1.2.3
  → task def revision (image = <ecr>:v1.2.3)        compute/main.tf:172
  → ECS rolling deploy (min 50% healthy, max 200%)  :233-234
  → new task pulls image (execution role, ECR)      :14-27
  → container health: localhost:8000/health         :192-198
       healthy after 2 passes?  20s start + 2×30s ≈ 80s
  → ALB health: GET /health matcher 200             :101-110
       2×30s to join, 5×30s ≈ 150s to evict
  → all healthy? → old tasks drained. Any failure → circuit breaker :228-231
       → rollback = true → service reverts to last good revision
```

### 4.4 compute — autoscaling decision

```
input:  avg CPU across API tasks (1-minute samples)
formula: if avg > 70% → add tasks (max api_max_count); if avg < 70% → remove (after 300s cool)
output:  2 tasks @ 85% → scale out +1 task (again allowed after 60s)
         2 tasks @ 40% → wait 300s → scale in −1 task, never below min_count
```
Guard: scaling never exceeds `[min_capacity, max_capacity]` (compute/main.tf:249-250).

### 4.5 qdrant — environment assembly

```
input:  qdrant_api_key = "s3cr3t-key-9f2"
formula: base_env ++ (api_key != "" ? [{ API_KEY = api_key }] : [])
output:  5 env entries (storage, snapshots, grpc, log level, api key)
         with qdrant_api_key = "" → 4 entries, Qdrant runs unauthenticated
```
Source: `modules/qdrant/main.tf:35-44` (the ternary on line 43 is the guard).

### 4.6 redis — two modes

```
dev (1 node):            staging/production (HA):
num_cache_clusters=1     num_cache_clusters=2
automatic_failover=false automatic_failover=true
multi_az=false           multi_az=true
snapshot_retention=1     snapshot_retention=7 (production/main.tf:45)
→ single endpoint        → primary (write) + reader (read) endpoints
```
Failover guard: multi-AZ with failover is only valid when `num_cache_clusters ≥ 2`
(documented in `modules/redis/variables.tf:22-26`).

### 4.7 registry — image retention

```
input:  25 tagged images (v1 … v25), 3 untagged
rule1:  untagged && pushed > 1 day ago → delete all 3
rule2:  tagged "v*" && count(25) > keep(10) → delete 15 oldest
output: 10 tagged images (v16 … v25) remain
```
Source: `modules/registry/main.tf:19-44`; production raises keep-count to 20
(`environments/production/main.tf:32`).

### 4.8 observability — alarm evaluation

```
CPU/memory alarm:  ALARM iff N consecutive 60s averages > threshold
  N=2: samples [85%, 90%] → breach×2 → ALARM
       samples [85%, 60%] → breach×1 → stays OK
5xx alarm:         Sum of errors in 1 minute > threshold (5 default, 1 prod) → ALARM
missing data:      treated as notBreaching → no false pages in quiet periods
```
Source: `modules/observability/main.tf:19-96` (evaluation_periods 22/49/76, treat_missing_data 29/56/83).
Note: the 5xx alarm has **no `ok_actions`** — it never announces recovery (:73-96).

---

## 5. Event Lifecycle — deploying `v1.2.3` to dev

| # | Actor | Action | Concrete value |
|---|---|---|---|
| 1 | Operator | `terraform apply -var=image_tag=v1.2.3` in `terraform/environments/dev` | — |
| 2 | Terraform | Locks + reads state | `s3://ai-backend-api-tfstate-123456789012/dev/terraform.tfstate` |
| 3 | Terraform | Computes diff | 1 to update: `aws_ecs_task_definition.api` |
| 4 | Terraform → AWS | Registers new task def revision; image = `${ecr_url}/ai-backend-api-dev-api:v1.2.3` | compute/main.tf:172 |
| 5 | ECS | Rolling deploy: launches 1 new task beside the old one (50%/200%) | compute/main.tf:233-234 |
| 6 | ECS agent | Assume `execution_role` → pull image from ECR | compute/main.tf:14-27 |
| 7 | Container | uvicorn boots on :8000; `HEALTHCHECK` probes `/health` (20s start, 3 retries) | Dockerfile:50-51, compute/main.tf:192-198 |
| 8 | ALB | `GET /health` on new task IP; needs 2×200s @30s to route traffic | compute/main.tf:101-110 |
| 9 | ECS | Old task drained; circuit breaker rolls back if new tasks stay unhealthy | compute/main.tf:228-231 |
| 10 | Autoscaler | Keeps avg CPU at 70% between 1–4 tasks | compute/main.tf:245-267 |
| 11 | Request | `https://<alb-dns>/api/chat` → :443 (TLS13 policy, ACM cert) → TG :8000 → uvicorn | compute/main.tf:135-146 |
| 12 | App | `/health` pings Redis+Qdrant+OpenAI; all OK → 200, any down → 503 | app/main.py:99-137 |
| 13 | Observability | Logs stream to `/ecs/ai-backend-api-dev/api`; breaches → SNS → `alarm_email` | compute/main.tf:149-157, observability/main.tf:2-16 |

---

## 6. Full-Stack Flow (swimlane)

```
 Operator          Terraform CLI            Root Module            AWS                    Running App
    │                   │                       │                  │                          │
    │ apply             │                       │                  │                          │
    ├──────────────────►│ lock S3 state         │                  │                          │
    │                   ├──────────────────────►│ fan-out to 6     │                          │
    │                   │                       │ modules in DAG   │                          │
    │                   │                       │ order (§4)       │                          │
    │                   │                       ├─────────────────►│ create VPC/SGs/EFS       │
    │                   │                       ├─────────────────►│ create ECR/Redis         │
    │                   │                       ├─────────────────►│ create ALB/ECS/tasks     │
    │                   │                       ├─────────────────►│ create SNS/alarms        │
    │                   │ write new state       │                  │                          │
    │◄──────────────────┤ outputs: alb_dns_name │                  │                          │
    │                   │                       │                  │   ECS pulls image v1.2.3 │
    │                   │                       │                  ├─────────────────────────►│ uvicorn :8000
    │                   │                       │                  │                          │
    │  GET https://<alb_dns>/api/chat  ────────────────────────────────────────────────────────► │
    │◄──────────────────────────────────────────────────── 200 JSON (or 503 from /health) ◄─────│
    │                   │                       │                  │  alarms → SNS → email    │
```

---

## 7. Design Decisions

### 7.1 "Why X instead of Y"

| Decision | Why | What breaks without it |
|---|---|---|
| S3 lockfile (`use_lockfile = true`) | One less stateful resource to babysit | Two concurrent applies race and corrupt state |
| SG chaining by SG id | Trust follows role, not network position | `10.0.0.0/16` CIDR ingress would let any private host hit Redis |
| NAT single-AZ (network/main.tf:58-80) | ~$32/mo saved per extra AZ | Comment admits it: other-AZ private egress dies with that AZ |
| `target_type = "ip"` (compute/main.tf:99) | Fargate `awsvpc` tasks register by ENI IP | `instance` type finds no targets; deploys never pass health checks |
| EFS for Qdrant (qdrant/main.tf:2-21) | Fargate has no attachable disk; EFS survives every deploy | Vector data wiped on every task restart |
| Pinned `qdrant/qdrant:v1.14.0` | Upgrades become conscious decisions | `:latest` auto-upgrades and can break storage format |
| IMMUTABLE tags in prod (production/main.tf:31) | A tag always means the same bytes | Silent tag overwrite → untraceable rollback targets |
| Separate exec vs task role (compute/main.tf:14-60) | Agent needs ECR/logs; app needs SSM/secrets | One fat role = over-privileged app |
| 301 HTTP listener (compute/main.tf:119-132) | Cheap enforced HTTPS | :80 would serve plaintext or drop requests |
| Circuit breaker + rollback (compute/main.tf:228-231) | Bad deploys self-heal | Service wedges retrying a doomed revision |
| `treat_missing_data = "notBreaching"` (observability/main.tf:29,56,83) | No metrics ≠ outage | Quiet periods page on non-existent failures |
| Env state files `dev/staging/production` (env main.tf:12) | Zero blast-radius coupling between envs | One bad apply damages every environment |

### 7.2 Known gaps (read before relying on this stack)

1. `env_vars` is **never passed** by any root module (grep: only `compute/main.tf:179-181` consumes it).
   `REDIS_HOST`/`QDRANT_HOST` (README:128-129) are therefore not injected — the API
   would default to `localhost` (settings.py:27,61) unless set out-of-band.
2. Redis module outputs (`primary_endpoint`, `reader_endpoint`) are dangling — nothing consumes them,
   so Redis/Qdrant endpoints are not wired into the app's environment by Terraform.
3. `transit_encryption_enabled = true` (redis/main.tf:30) requires TLS clients (`rediss://` + AUTH),
   but `RedisSettings.url` builds plain `redis://` (app/core/config/settings.py:33-37).
4. Bootstrap lock pins aws 5.100.0 while env lock files contain 6.36.0, though every
   root module declares `~> 5.0` — the 6.x lock contradicts the constraint.
5. Root `terraform/versions.tf` lives in no root-module directory; each env re-declares pins.
6. The 5xx alarm lacks `ok_actions`, so it never notifies on recovery (observability/main.tf:85).
7. `task_role` grants SSM/secrets read (compute/main.tf:44-59) but no container defines a
   `secrets:` block — prepared, unused.

---

## 8. Edge Cases Table

| Scenario | How handled | Source |
|---|---|---|
| Concurrent `terraform apply` runs | S3 lockfile blocks the second run | env main.tf:15 |
| Empty `auth_token` | Ternary yields `null` → no Redis AUTH | redis/main.tf:33 |
| Empty `qdrant_api_key` | Key env entry omitted entirely | qdrant/main.tf:43 |
| Empty `alarm_email` | `count = 0` → no subscription created | observability/main.tf:12 |
| No metrics (quiet period) | `treat_missing_data = notBreaching` — no false alarm | observability/main.tf:29,56,83 |
| Bad image revision deployed | Circuit breaker rolls back automatically | compute/main.tf:228-231 |
| Task fails container health 3× | Marked unhealthy, replaced; ALB evicts after 5 misses | compute/main.tf:192-198,101-110 |
| CPU spike | Target tracking scales out (60s cooldown), capped at max_count | compute/main.tf:253-267 |
| AZ-B failure | EFS still reachable via other-AZ mount target; but NAT egress dies (single NAT) | network/main.tf:16-21,58-80 |
| Tag overwrite attempt in production | ECR rejects push (`IMMUTABLE`) | production/main.tf:31 |
| 25+ tagged images accumulate | Lifecycle policy deletes beyond keep-count | registry/main.tf:32-42 |
| Stale image with `latest` | Rolling deploy replaces tasks; mutable tags make this ambiguous (see §7.2 #3) | compute/main.tf:172 |
| Terraform state destroyed by accident | Bucket `force_destroy = false` blocks it | bootstrap/main.tf:46 |
| HTTPS listener not ready | Service `depends_on` https listener prevents dead listener deploys | compute/main.tf:236 |

---

## 9. Integration Point

Canonical call site — `terraform/environments/dev/main.tf:48-67`, the block that wires the API:

```hcl
module "compute" {
  source             = "../../modules/compute"        # child module directory
  project            = var.project                    # "ai-backend-api" → all names
  environment        = var.environment                # "dev" → state key, tags, names
  aws_region         = var.aws_region                 # for awslogs + SSM ARNs
  aws_account_id     = var.aws_account_id             # builds SSM/secrets ARNs (compute:54-55)
  vpc_id             = module.network.vpc_id          # target group must live in this VPC
  public_subnet_ids  = module.network.public_subnet_ids   # ALB attaches here (internet-facing)
  private_subnet_ids = module.network.private_subnet_ids  # API tasks run here (no public IP)
  alb_sg_id          = module.network.alb_sg_id       # SG allowing 80/443 from internet
  api_sg_id          = module.network.api_sg_id       # SG allowing 8000 from ALB SG only
  ecr_repository_url = module.registry.repository_url # image source for task def
  image_tag          = var.image_tag                  # v1.2.3 → pinned deploy
  certificate_arn    = var.certificate_arn            # TLS cert for :443 listener
  api_cpu            = var.api_cpu                    # 512 = ½ vCPU
  api_memory         = var.api_memory                 # 1024 MiB = 1 GiB
  api_desired_count  = var.api_desired_count          # tasks running now
  api_min_count      = var.api_min_count              # autoscaling floor
  api_max_count      = var.api_max_count              # autoscaling ceiling
}
```

Deploy sequence (README.md:131-141):

```bash
cd terraform/bootstrap && terraform apply          # once: creates state bucket
cd terraform/environments/dev
terraform init && terraform apply                  # then fill bucket name into backend block
```

---

## 10. File Map

```
terraform/
├── versions.tf                      # root pins (no root module dir — informational)
├── bootstrap/
│   └── main.tf                      # one-time S3 state bucket (+versioning/encryption/block-public)
├── environments/
│   ├── dev/
│   │   ├── main.tf                  # wires 6 modules; s3 backend key dev/
│   │   ├── variables.tf             # 15 root variable schemas
│   │   └── terraform.tfvars         # dev values (permission-blocked here)
│   ├── staging/                     # same shape as dev
│   └── production/                  # + IMMUTABLE, 20 images, 7d snapshots, 70/70/1 thresholds
└── modules/
    ├── network/                     # VPC 10.0.0.0/16, 2+2 subnets, IGW, NAT, 5 SGs
    ├── registry/                    # ECR repo + lifecycle (untagged 1d, keep N "v" tags)
    ├── compute/                     # IAM, ECS cluster, ALB+listeners, API task/service, autoscaling
    ├── redis/                       # ElastiCache subnet group + replication group (6379, TLS)
    ├── qdrant/                      # EFS + Qdrant task/service (6333/6334, EFS at /qdrant/storage)
    └── observability/               # SNS alarms topic + CPU/memory/5xx alarms
app/
├── main.py                          # /health endpoint (200/503) probed by ALB + container
└── core/config/settings.py          # RedisSettings/QdrantSettings — reads REDIS_*/QDRANT_* env
Dockerfile                           # image deployed by compute module (uvicorn :8000, /health)
README.md:131-141                    # documented bootstrap + apply sequence
```

*End of deep dive.*
