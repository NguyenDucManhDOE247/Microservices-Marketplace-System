# Online Service Marketplace

**Graduation Thesis — Vietnam Japan University**

> Developing and Deploying an Online Service Marketplace System using Microservices Architecture with Automated CI/CD Pipeline on AWS Platform

A production-grade marketplace system where users can register, log in, browse service listings, place orders, make payments, and track order history. The system is built with a Microservices architecture, fully automated CI/CD pipeline, infrastructure-as-code, real-time monitoring, and automated operational scripts — all deployed on AWS.

---

## Table of Contents

- [Project Structure](#-project-structure)
- [Technology Stack](#-technology-stack)
- [Microservices Overview](#-microservices-overview)
- [Infrastructure — Terraform](#-infrastructure--terraform)
- [Configuration Management — Ansible](#-configuration-management--ansible)
- [CI/CD Pipeline — Jenkins](#-cicd-pipeline--jenkins)
- [Kubernetes Deployment](#-kubernetes-deployment)
- [Monitoring — Prometheus + Grafana](#-monitoring--prometheus--grafana)
- [Automated Testing — Jest](#-automated-testing--jest)
- [Automation Scripts — Python](#-automation-scripts--python)
- [Local Development](#-local-development)
- [Deployment Reference](#-deployment-reference)
- [Contributors](#-contributors)

---

## 📂 Project Structure

```
Online-Service-Marketplace/
├── frontend/                   # Vue 3 + Vite SPA
├── gateway/                    # NGINX reverse proxy / API gateway
├── user-service/               # User microservice (port 4001)
│   ├── src/
│   │   ├── app.js
│   │   ├── controllers/
│   │   ├── models/
│   │   └── routes/
│   └── tests/
├── product-service/            # Product microservice (port 4002)
├── order-service/              # Order microservice (port 4003)
├── payment-service/            # Payment microservice (port 4004)
├── k8s/                        # Kubernetes manifests
│   ├── namespace.yaml
│   ├── frontend.yaml
│   ├── nginx.yaml
│   ├── user.yaml / product.yaml / order.yaml / payment.yaml
│   ├── mongo.yaml
│   ├── hpa.yaml
│   ├── ingress.yaml
│   └── monitoring/
│       ├── prometheus.yaml
│       └── grafana.yaml
├── monitoring/                 # Source config files for monitoring stack
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── dashboards/
│           └── osm-dashboard.json
├── scripts/                    # Python automation scripts
│   ├── health_check.py
│   ├── backup_mongodb.py
│   └── cleanup_ecr.py
├── docker-compose.yaml         # Local development environment
├── Jenkinsfile                 # Declarative Jenkins pipeline
└── script.groovy               # Pipeline helper functions
```

---

## ⚙️ Technology Stack

| Category         | Technology                | Role                                                  |
| ---------------- | ------------------------- | ----------------------------------------------------- |
| Cloud            | AWS                       | Scalable infrastructure, pay-as-you-go                |
| IaC              | Terraform ≥ 1.10          | Provision entire AWS infrastructure with one command  |
| Configuration    | Ansible                   | Idempotent server configuration (Jenkins, MongoDB)    |
| CI/CD            | Jenkins + GitHub Webhook  | Push code → test → build → deploy automatically       |
| Registry         | Amazon ECR                | Private Docker image registry with IAM authentication |
| Orchestration    | Kubernetes / EKS          | Auto-restart, auto-scale, secrets management          |
| Frontend         | Vue 3 + Vue Router + Vite | Fast SPA, lightweight production build                |
| Backend          | Node.js + Express.js      | 4 independent REST API microservices                  |
| Database         | MongoDB (on EC2)          | Flexible schema, each service has its own database    |
| API Gateway      | NGINX                     | Reverse proxy routing all API calls to services       |
| Monitoring       | Prometheus + Grafana      | Real-time metrics collection and visualization        |
| Testing          | Jest + MongoMemoryServer  | Unit/integration tests without a real database        |
| Automation       | Python + boto3            | Health check, DB backup, ECR image cleanup            |
| Containerization | Docker                    | Consistent build and runtime environment              |

---

## 🧩 Microservices Overview

| Service           | Port | Responsibilities                              | Security                          |
| ----------------- | ---- | --------------------------------------------- | --------------------------------- |
| `user-service`    | 4001 | Register, login, JWT issuance, email lookup   | bcrypt password hashing           |
| `product-service` | 4002 | Product CRUD, listing                         | —                                 |
| `order-service`   | 4003 | Create orders, verify user existence via HTTP | JWT middleware, express-validator |
| `payment-service` | 4004 | Process payments, save payment records        | JWT middleware, express-validator |

**Key security implementation:**

- `auth.js` middleware reads `Authorization: Bearer <token>` → `jwt.verify()` → attaches `req.user`. Invalid or missing token → returns `401` immediately.
- Input validation with `express-validator` on all `POST` endpoints (email format, required fields, minimum length).

**Inter-service communication:**

- `order-service` calls `user-service /api/users/check/:email` via HTTP (axios) to verify user existence before creating an order.
- `payment-service` calls `order-service` to verify order validity before processing payment.

**Prometheus metrics on every service:**

- Each service exposes `/metrics` with `prom-client`, tracking `http_requests_total` and `http_request_duration_seconds`.

---

## 🏗️ Infrastructure — Terraform

All AWS infrastructure is defined as code across 5 Terraform modules and provisioned with a single `terraform apply`.

| Module | Resources Created                                                                                                                                |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `vpc/` | VPC `10.0.0.0/16`, 2 public subnets, 2 private subnets, Internet Gateway, NAT Gateway, route tables                                              |
| `iam/` | EKS role, EC2 instance profile for Jenkins (ECR + EKS + STS permissions)                                                                         |
| `ecr/` | 6 private ECR repositories: `osm-user-service`, `osm-product-service`, `osm-order-service`, `osm-payment-service`, `osm-frontend`, `osm-gateway` |
| `eks/` | EKS cluster `osm-cluster` with managed node group (private subnets, ap-southeast-1)                                                              |
| `ec2/` | Jenkins EC2 (public subnet) + MongoDB EC2 (private subnet, `10.0.10.45`)                                                                         |

```bash
cd terraform/
terraform init
terraform apply        # Provision everything (~10 minutes)
terraform output       # View IPs and cluster info
terraform destroy      # Clean teardown, no cost when not in use
```

---

## 🔧 Configuration Management — Ansible

After Terraform provisions the servers, Ansible configures them automatically in a single command.

```bash
# Update inventory with Terraform output IPs
terraform output ips > inventory/hosts.yml

# Configure all servers
ansible-playbook playbook.yml -i inventory/hosts.yml
```

**3 Ansible roles:**

| Role      | What it installs/configures                                                                                       |
| --------- | ----------------------------------------------------------------------------------------------------------------- |
| `jenkins` | Java 17, Jenkins LTS, Docker, AWS CLI, kubectl, kubeconfig for EKS                                                |
| `mongodb` | MongoDB 7.0, authentication enabled, bind to private IP only, backup script at `/usr/local/bin/mongodb-backup.sh` |
| `common`  | System packages, timezone, security hardening                                                                     |

A successful run shows `failed=0` — confirmation that all servers are configured correctly and idempotently.

---

## 🚀 CI/CD Pipeline — Jenkins

Push code to GitHub → GitHub Webhook triggers Jenkins → full pipeline runs automatically.

### 12 Pipeline Stages

| #   | Stage                    | What it does                                                                                                                               | Branch            |
| --- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------------- |
| 1   | **Skip CI Check**        | Fix root-owned files from Docker test runs, read commit message — if `[skip ci]` is present → skip all stages                              | All               |
| 2   | **Init**                 | `aws sts get-caller-identity` to fetch AWS Account ID dynamically, set ECR registry URL, configure namespace and image tag based on branch | All               |
| 3   | **Checkout Code**        | `checkout scm` — fetch source code for the current branch                                                                                  | All               |
| 4   | **Validate**             | Check `package.json` syntax, `kubectl --dry-run`, `terraform fmt`                                                                          | `refactor/*` only |
| 5   | **Read Version**         | Read version from `package.json` (e.g. `1.0.22`) → set as image tag                                                                        | `main` only       |
| 6   | **Run Tests**            | Run Jest inside `node:22-slim` Docker container for all 4 services with MongoMemoryServer. Requires 100% coverage.                         | `main`, `dev`     |
| 7   | **Build Docker Images**  | Build 6 images. `main` → 2 tags (`:1.0.22` + `:latest`). `dev` → 1 tag (`:dev-<build>-<sha>`)                                              | `main`, `dev`     |
| 8   | **Push to ECR**          | `aws ecr get-login-password` → `docker login` → push. No stored credentials — uses IAM Role on Jenkins EC2                                 | `main`, `dev`     |
| 9   | **Cleanup Docker**       | Remove dangling images, build cache older than 24h, stopped containers, local dev images already pushed                                    | `main`, `dev`     |
| 10  | **Deploy to Kubernetes** | `aws eks update-kubeconfig` → verify prerequisites (Ingress Controller, metrics-server) → `kubectl apply`                                  | `main`, `dev`     |
| 11  | **Verify Deployment**    | `kubectl rollout status` for each deployment with 120s timeout — ensures all pods are `Running`                                            | `main`, `dev`     |
| 12  | **Bump Version**         | Increment patch version, `git commit [skip ci]`, push back to GitHub                                                                       | `main` only       |

### Multi-Environment Strategy

| Branch       | Environment     | Namespace | Image Tag            | Extra                               |
| ------------ | --------------- | --------- | -------------------- | ----------------------------------- |
| `main`       | Production      | `osm`     | `:1.0.x` + `:latest` | Monitoring deployed, version bumped |
| `dev`        | Development     | `osm-dev` | `:dev-<build>-<sha>` | No version bump                     |
| `refactor/*` | Validation only | —         | Not built            | Syntax/format checks only           |

**AWS Account ID is never hardcoded.** Jenkins EC2 has an IAM Role attached — `aws sts get-caller-identity` retrieves the Account ID at runtime from the EC2 metadata service. No credentials are stored in code or Jenkins configuration.

**Infinite loop prevention:** The Bump Version stage commits with `[skip ci]` in the message. Stage 1 detects this and exits immediately, preventing Jenkins from triggering itself again.

---

## ☸️ Kubernetes Deployment

### Namespaces

| Namespace       | Purpose                           | Created by                       |
| --------------- | --------------------------------- | -------------------------------- |
| `osm`           | Production workloads              | `k8s/namespace.yaml`             |
| `osm-dev`       | Development workloads             | Pipeline (`dev` branch)          |
| `monitoring`    | Prometheus + Grafana              | `k8s/monitoring/prometheus.yaml` |
| `ingress-nginx` | NGINX Ingress Controller          | `installClusterPrerequisites()`  |
| `kube-system`   | metrics-server (required for HPA) | `installClusterPrerequisites()`  |

### Key Resources

**ConfigMap & Secret — centralized configuration:**

- `ConfigMap osm-config` → service URLs, environment settings
- `Secret osm-secrets` → `JWT_SECRET`, MongoDB URI with credentials

Config is injected into pods at startup. Changing configuration does not require rebuilding images.

**Deployments with health probes:**

- `readinessProbe` — pod only receives traffic once it's ready
- `livenessProbe` — pod is automatically restarted if it becomes unhealthy
- Applied to all 6 services (4 backends + frontend + gateway)

**HPA — Horizontal Pod Autoscaler:**

- CPU > 70% or Memory > 80% → Kubernetes scales: `2 → 3 → 4 → 5` replicas
- Load drops → automatically scales back down to 2 replicas
- Applied to all 4 microservices, frontend, and gateway

**NGINX Ingress Controller:**

- Single LoadBalancer ELB as the entry point for all traffic
- Routes `/api/users` → `user-service`, `/api/products` → `product-service`, etc.
- Routes `/` → `frontend`

### Deploying to the Cluster

```bash
# Apply all manifests
kubectl apply -f k8s/

# Check status
kubectl get pods -n osm
kubectl get svc -n osm
kubectl get ingress -n osm

# Apply monitoring stack (order matters)
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/monitoring/prometheus.yaml
kubectl apply -f k8s/monitoring/grafana.yaml
```

---

## 📊 Monitoring — Prometheus + Grafana

### How it works

Each of the 4 backend services exposes a `/metrics` endpoint using `prom-client`. Prometheus automatically discovers these pods via Kubernetes Service Discovery and scrapes metrics every 15 seconds. Grafana reads from Prometheus and displays the pre-provisioned dashboard.

**Auto-discovery** — no manual service registration needed. Adding the following annotation to any pod YAML is all that's required:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "4001"
  prometheus.io/path: "/metrics"
```

**RBAC security** — Prometheus runs with its own `ServiceAccount` and a `ClusterRole` that permits only reading pod/endpoint lists. No `cluster-admin` privileges.

**Pre-provisioned dashboard** — Grafana dashboard is loaded automatically via `ConfigMap` on startup. No manual setup required.

### OSM Microservices Dashboard (6 panels)

| Panel                    | Metric                                    | What it shows                   |
| ------------------------ | ----------------------------------------- | ------------------------------- |
| HTTP Request Rate        | `http_requests_total`                     | Requests per second per service |
| Request Duration p95     | `http_request_duration_seconds`           | 95th percentile latency in ms   |
| Error Rate 5xx           | `http_requests_total{status_code=~"5.."}` | Server errors per second        |
| Total Requests (last 5m) | `http_requests_total`                     | Stat card per service           |
| Memory Usage             | `nodejs_heap_used_bytes`                  | Heap memory in MB per service   |
| CPU Usage Rate           | `osm_process_cpu_seconds_total`           | CPU % per service               |

### Access

| Service    | Access                                                                                                             |
| ---------- | ------------------------------------------------------------------------------------------------------------------ |
| Grafana    | `http://<grafana-elb>:3000` — Login: `admin` / `OsmGrafana2024!`                                                   |
| Prometheus | Internal only (ClusterIP). Port-forward when needed: `kubectl port-forward -n monitoring svc/prometheus 9090:9090` |

---

## 🧪 Automated Testing — Jest

All 4 microservices have full test coverage, run automatically in Stage 6 of the CI/CD pipeline.

**Test infrastructure:** Jest + `mongodb-memory-server` — tests run against an in-memory MongoDB instance with no external dependencies. Tests run inside a `node:22-slim` Docker container in Jenkins.

**Coverage requirement:** 100% on all 4 services. Pipeline fails if coverage drops.

### Test Cases Summary

**user-service:** Register (success, invalid email, short password, duplicate email), Login (success, wrong password, user not found), `GET /check/:email` (exists, not found), `GET /metrics`, unknown route 404.

**product-service:** `GET /` listing, `POST /` create product, `GET /:id`, `PUT /:id`, `DELETE /:id`, `GET /metrics`, unknown route 404.

**order-service:** No token (401), invalid token (401), create order with valid user (201), user not found (400), user-service unreachable (500), missing fields (422), `GET /metrics`, unknown route 404.

**payment-service:** No token (401), invalid token (401), create payment (201), missing fields (422), `GET /metrics`, unknown route 404.

```bash
# Run tests locally for a service
cd user-service
npm test -- --coverage
```

---

## 🐍 Automation Scripts — Python

Located in `scripts/`. All scripts support a `--dry-run` flag to preview actions without executing them.

### `health_check.py` — System Health Monitor

Checks Kubernetes pod/deployment status and HTTP endpoint availability via the Ingress URL.

```bash
python scripts/health_check.py --namespace osm --base-url http://<INGRESS_IP>
python scripts/health_check.py --skip-k8s --base-url http://<INGRESS_IP>
```

Exit code `0` = all healthy. Exit code `1` = one or more checks failed. Suitable for use in cron jobs or post-deploy verification.

### `backup_mongodb.py` — MongoDB Backup to S3

Connects to the MongoDB EC2 (private subnet) via SSH using `paramiko`, runs the backup script installed by Ansible, downloads the archive via SFTP, uploads to S3, and applies a retention policy.

```bash
python scripts/backup_mongodb.py --key-file osm-key.pem
python scripts/backup_mongodb.py --key-file osm-key.pem --retain 30 --dry-run
```

**Requirements:** Run from Jenkins EC2 (same VPC as MongoDB). Jenkins IAM role needs `s3:PutObject`, `s3:ListBucket`, `s3:DeleteObject` permissions.

### `cleanup_ecr.py` — ECR Image Cleanup

For each `osm-*` ECR repository: deletes all untagged images immediately, keeps the K most recent tagged images and deletes older ones.

```bash
python scripts/cleanup_ecr.py --keep 10
python scripts/cleanup_ecr.py --dry-run   # Preview: "Would delete: osm-user-service:dev-5"
```

**Environment variables:** `AWS_REGION`, `ECR_KEEP`, `ECR_DRY_RUN`.

---

## 💻 Local Development

Run the entire system locally with Docker Compose:

```bash
docker-compose up --build
```

Services will be available at:

- Frontend: `http://localhost:80`
- user-service: `http://localhost:4001`
- product-service: `http://localhost:4002`
- order-service: `http://localhost:4003`
- payment-service: `http://localhost:4004`

---

## 📎 Deployment Reference

| Component       | Details                                                                                                                         |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| AWS Region      | `ap-southeast-1` (Singapore)                                                                                                    |
| AWS Account     | `825621302666`                                                                                                                  |
| EKS Cluster     | `osm-cluster`                                                                                                                   |
| ECR Registry    | `825621302666.dkr.ecr.ap-southeast-1.amazonaws.com`                                                                             |
| Jenkins EC2     | Public subnet, IAM Role for ECR + EKS + STS (no stored credentials)                                                             |
| MongoDB EC2     | Private subnet `10.0.10.45` — not accessible from internet                                                                      |
| GitHub Repo     | [NguyenDucManhDOE247/Microservices-Marketplace-System](https://github.com/NguyenDucManhDOE247/Microservices-Marketplace-System) |
| App Namespace   | `osm` (production), `osm-dev` (development)                                                                                     |
| Node.js Version | `22-alpine` (all backend services)                                                                                              |

### Useful kubectl Commands

```bash
# Check all resources in production namespace
kubectl get all -n osm

# Check monitoring stack
kubectl get pods -n monitoring
kubectl get svc -n monitoring

# View logs for a service
kubectl logs -n osm deployment/user-service

# Check HPA status
kubectl get hpa -n osm

# Force restart a deployment
kubectl rollout restart deployment/user-service -n osm

# Check ingress
kubectl get ingress -n osm
```

---

## 👤 Contributors

**Nguyen Duc Manh**
BCSE2022 — Vietnam Japan University

---

## 📄 License

This project is licensed under the MIT License.
