# Argus — LLM-Driven Business KPI & Advisory Portal

**Argus** converts raw CSV/XLSX data and a short business description into approved, validated KPIs and a consultant-style advisory report — in minutes.

---

## Overview

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite — deployable to AWS Amplify |
| Backend API | FastAPI on AWS ECS Fargate |
| Worker | Async worker process (same Docker image, different entrypoint) polling SQS |
| Storage | S3 (uploads & report artifacts) |
| Database | DynamoDB (single-table design) |
| Queue | SQS |
| LLM | OpenAI API (GPT-4o-mini by default, configurable) |
| Observability | CloudWatch Logs & Container Insights |
| Secrets | AWS Secrets Manager |
| Infrastructure | CloudFormation (`infra/cloudformation/template.yaml`) |

---

## User Flow

1. **Upload** — User uploads CSV/XLSX and enters a short business description.
2. **Profile** — Data profiler detects columns, types, dates, IDs, missingness, and joinability.
3. **KPI Generation** — LLM proposes 5–8 KPI definitions with formulas and rationale.
4. **KPI Approval** *(human gate)* — User approves or rejects each KPI. **No computation happens without explicit approval.**
5. **KPI Computation** — Worker executes approved KPIs via plan-to-Pandas (no `eval()`).
6. **Advisory Report** — LLM generates risks, compliance notes, forecasts, and recommendations.
7. **Recommendation Approval** *(human gate)* — Recommendations affecting pricing, compliance, or operations require explicit human approval.

---

## Repository Structure

```
Argus/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI application
│   │   ├── config.py          # Settings (pydantic-settings / env vars)
│   │   ├── models.py          # Pydantic domain models
│   │   ├── routers/           # API route handlers
│   │   │   ├── projects.py
│   │   │   ├── datasets.py
│   │   │   ├── kpis.py
│   │   │   ├── jobs.py
│   │   │   └── reports.py
│   │   ├── services/          # Core business logic
│   │   │   ├── database.py    # DynamoDB service
│   │   │   ├── storage.py     # S3 service
│   │   │   ├── queue.py       # SQS service
│   │   │   ├── profiler.py    # Data Profiler
│   │   │   ├── llm.py         # LLM service (OpenAI)
│   │   │   └── kpi_engine.py  # Plan-to-Pandas KPI execution
│   │   └── worker/
│   │       └── main.py        # Async worker entrypoint
│   ├── tests/
│   │   ├── test_profiler.py
│   │   ├── test_kpi_engine.py
│   │   └── test_models.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/client.ts      # Typed API client
│   │   ├── pages/
│   │   │   ├── UploadPage.tsx
│   │   │   ├── KPIApprovalPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   └── ReportPage.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
└── infra/
    └── cloudformation/
        └── template.yaml      # Full AWS infrastructure stack
```

---

## Plan-to-Pandas (Security)

Instead of executing arbitrary LLM-generated code, the LLM outputs a **structured JSON plan**:

```json
{
  "metric": "sum",
  "column": "revenue",
  "filters": [{"column": "status", "operator": "eq", "value": "paid"}],
  "time_column": "created_at",
  "time_window_days": 30
}
```

The `kpi_engine` translates this plan into safe, deterministic Pandas operations — no `eval()`, no `exec()`. This makes computation auditable and eliminates code-injection risks.

---

## Local Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run API server (requires AWS credentials and .env file)
uvicorn app.main:app --reload
```

**Environment variables** (create `backend/.env`):
```
OPENAI_API_KEY=sk-...
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=argus
S3_BUCKET_NAME=argus-uploads-<account>-development
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/<account>/argus-jobs-development
CORS_ORIGINS=["http://localhost:3000"]
```

### Worker

```bash
cd backend
python -m app.worker.main
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
```

Set `VITE_API_URL` in `frontend/.env` to point at your API (default proxied to `http://localhost:8000`).

---

## Docker

```bash
# Build
docker build -t argus:latest backend/

# Run API
docker run -p 8000:8000 --env-file backend/.env argus:latest

# Run Worker
docker run --env-file backend/.env argus:latest python -m app.worker.main
```

---

## Infrastructure Deployment

```bash
aws cloudformation deploy \
  --template-file infra/cloudformation/template.yaml \
  --stack-name argus-production \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      AppEnv=production \
      ImageUri=<ECR_IMAGE_URI> \
      OpenAISecretArn=<SECRET_ARN> \
      VpcId=<VPC_ID> \
      SubnetIds=<SUBNET1>,<SUBNET2> \
      CorsOrigins=https://main.CHANGEME.amplifyapp.com
```

---

## Data Privacy & Audit Trail

- Files stored in S3 with server-side AES-256 encryption and least-privilege IAM.
- Prompts include only necessary schema fields; PII columns can be excluded at upload time.
- Full audit trail: all prompts, LLM outputs, approval decisions, and computed KPIs are persisted in DynamoDB.

---

## Human-in-the-Loop Requirements

| Gate | When | Effect |
|---|---|---|
| KPI Approval | After LLM proposes KPIs | No KPI computation until approved |
| Recommendation Approval | After advisory report is generated | Recommendations affecting pricing/compliance/operations require explicit sign-off |
