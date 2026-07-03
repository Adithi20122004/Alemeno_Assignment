# Transaction Cleaner — FastAPI + Celery + Gemini

Production-quality backend that ingests a transactions CSV, cleans it, detects
anomalies, categorises unlabelled rows with **Gemini 1.5 Flash**, and produces a
JSON summary + risk assessment. Fully containerised with **Docker Compose**.

---

## Architecture

```mermaid
flowchart LR
    Client[Client / curl / Postman]
    API[FastAPI<br/>REST API]
    Redis[(Redis<br/>Broker + Result Backend)]
    Worker[Celery Worker<br/>process_job pipeline]
    Gemini[Gemini 1.5 Flash API]
    PG[(PostgreSQL)]

    Client -- POST /jobs/upload --> API
    API -- enqueue --> Redis
    API -- persist Job --> PG
    Redis -- deliver task --> Worker
    Worker -- LLM calls --> Gemini
    Worker -- write cleaned txns + summary --> PG
    Client -- GET /jobs, /status, /results --> API
    API -- read --> PG
```

T\docs\architecture.png

---

## Folder Structure

```
backend/
├── app/
│   ├── api/routes/jobs.py       # REST endpoints
│   ├── core/                    # config, logging, celery bootstrap
│   ├── database/session.py      # SQLAlchemy engine + Base + get_db()
│   ├── llm/                     # Gemini client + prompts (with retries)
│   ├── models/                  # Job, Transaction, JobSummary
│   ├── repositories/            # Repository pattern (data access)
│   ├── schemas/                 # Pydantic v2 request/response models
│   ├── services/                # CSV cleaner, anomaly detector, summariser
│   ├── tasks/process_job.py     # Celery pipeline (steps 1-7)
│   ├── workers/celery_worker.py # Celery entrypoint
│   ├── utils/file_utils.py      # Safe upload persistence
│   └── main.py                  # FastAPI factory
├── alembic/                     # DB migrations
├── sample_data/transactions.csv # Provided sample dataset
├── tests/                       # pytest unit tests for pipeline
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your Gemini key:

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy Postgres URL | `postgresql+psycopg2://postgres:postgres@postgres:5432/txndb` |
| `CELERY_BROKER_URL` | Redis broker | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Redis result backend | `redis://redis:6379/1` |
| `GEMINI_API_KEY` | Google AI Studio key | *required* |
| `GEMINI_MODEL` | Gemini model | `gemini-1.5-flash` |
| `GEMINI_MAX_RETRIES` | LLM retry count | `3` |
| `GEMINI_RETRY_BASE_SECONDS` | Exponential backoff base | `2` |
| `UPLOAD_DIR` | Where uploaded CSVs land | `/app/uploads` |
| `MAX_UPLOAD_MB` | Upload size limit | `20` |

Get a Gemini key at <https://aistudio.google.com/app/apikey>.

---

## How to Run

Zero-setup — Docker Compose spins up **Postgres + Redis + API + Celery Worker + Beat**:

```bash
cd backend
cp .env.example .env
# edit .env, paste your GEMINI_API_KEY
docker compose up --build
```

The API is now live at **http://localhost:8000** with Swagger docs at **http://localhost:8000/docs**.

The API container automatically runs `alembic upgrade head` at boot, so the schema is ready.

### Migrations (manual)

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "your message"
docker compose exec api alembic downgrade -1
```

### Running tests

```bash
docker compose exec api pytest -v
```

---

## Example curl Requests

Upload a job (the provided sample CSV lives in `sample_data/`):

```bash
curl -X POST http://localhost:8000/jobs/upload \
    -F "file=@sample_data/transactions.csv"
```

Response:

```json
{
  "job_id": 1,
  "status": "PENDING",
  "filename": "transactions.csv",
  "message": "Job accepted. Processing in background."
}
```

List all jobs (optionally filter by status):

```bash
curl "http://localhost:8000/jobs"
curl "http://localhost:8000/jobs?status=COMPLETED"
```

Check a job's status (includes summary once completed):

```bash
curl http://localhost:8000/jobs/1/status
```

Fetch full results (cleaned transactions, anomalies, LLM summary):

```bash
curl http://localhost:8000/jobs/1/results | jq
```

Sample results payload (truncated):

```json
{
  "job": {"id": 1, "status": "COMPLETED", "row_count_raw": 95, "row_count_clean": 82, "...": "..."},
  "summary": {
    "total_spend_inr": 512983.44,
    "total_spend_usd": 27412.11,
    "top_merchants": [
      {"merchant": "Amazon", "total_amount": 143210.55},
      {"merchant": "Flipkart", "total_amount": 98421.30},
      {"merchant": "IRCTC", "total_amount": 62190.10}
    ],
    "anomaly_count": 7,
    "narrative": "Spending is dominated by e-commerce (Amazon, Flipkart) with heavy travel outflow. Seven anomalies detected including USD-denominated Swiggy/Ola transactions and outsized withdrawals on ACC004.",
    "risk_level": "HIGH"
  },
  "transactions": [ ... ],
  "anomalies": [ ... ]
}
```

---

## Pipeline (Celery Task)

1. **Read** the uploaded CSV with pandas.
2. **Clean**: normalise dates (multi-format), strip `$`, uppercase currency & status, drop duplicates by `txn_id`.
3. **Persist** cleaned rows to `transactions`.
4. **Anomaly detection** (rule-based):
   - `amount > 3 × median(amount) per account_id`
   - `currency == USD` combined with domestic merchants (`Swiggy`, `Ola`, `IRCTC`).
5. **LLM categorisation** for rows with missing `category` (Gemini 1.5 Flash, batched, retried 3× with exponential backoff). On permanent failure the row's `llm_failed` flag is set and processing continues.
6. **LLM summary** — one call producing JSON with totals, top-3 merchants, narrative, and `LOW / MEDIUM / HIGH` risk level. Falls back to a deterministic summariser if the LLM fails.
7. **Mark job COMPLETED** with row counts and `completed_at`.

---

## Quality Notes

- Repository + service layering, DI via FastAPI `Depends`.
- Pydantic v2 request/response schemas — every endpoint is typed.
- Config exclusively via `.env` / `pydantic-settings`, no hardcoded secrets.
- Structured logging, exception handling at task boundaries.
- Alembic-managed migrations, deterministic schema.
- `tenacity`-driven exponential-backoff retries on all Gemini calls; LLM failure never fails the job.
- Unit tests for the CSV → anomaly → summary chain (`pytest tests/`).

---

## Screenshots
docs/swagger.png
docs/results.png

