# RunForge

**A workload orchestration platform for engineering teams.**

RunForge gives teams one place to define operational workloads, create execution runs, track individual attempts, and inspect outcomes. The project is intentionally built in small, testable layers: a reliable local execution path first, then asynchronous delivery, isolated runtimes, scheduling, and production operations capabilities.

## Status

RunForge has a working local execution slice. Teams, Jobs, JobRuns, Attempts, a polling worker, retries, database migrations, and API tests are implemented.

Redis Streams, Docker-based workload isolation, cancellation, scheduling, authentication, observability, and cloud deployment are planned and are not represented as completed features.

## What it does today

- Manage Teams and their Jobs through a FastAPI API.
- Enforce unique Job names within each Team.
- Create a durable `JobRun` and its first `JobAttempt` together.
- Inspect and filter runs; inspect attempts and attempt history.
- Run queued work with a local PostgreSQL-polling worker.
- Retry failed work up to three times under the same `JobRun`.
- Return consistent API errors: `422` for invalid input, `404` for missing resources, and `409` for conflicts.
- Protect execution history by preventing deletion of a Job with Runs or a Team with Jobs.
- Exercise the API, worker, executor, and exception behavior with pytest.

## Core concepts

| Concept | Description |
|---|---|
| **Team** | The group that owns one or more Jobs. |
| **Job** | A saved workload definition, including its executor type and image reference. |
| **JobRun** | One requested execution of a Job. |
| **JobAttempt** | One attempt to complete a JobRun; retries create additional Attempts. |

```text
Team
└── Job
    └── JobRun
        ├── Attempt #1: FAILED
        └── Attempt #2: SUCCESS
```

A Job is a definition, not an execution. A retry remains part of the same JobRun so the execution history is preserved.

## Architecture

### Current local architecture

```text
API client
    │
    ▼
FastAPI API ───────────────► PostgreSQL
    │                            │
    │ creates QUEUED runs         │ source of truth
    ▼                            ▼
Response                    Local worker
                                  │
                                  ▼
                           Built-in executor
```

- **FastAPI** validates requests and exposes the control-plane API.
- **PostgreSQL** is the authoritative store for Teams, Jobs, Runs, Attempts, and their statuses.
- **The local worker** polls PostgreSQL for queued work, executes it, and records the result.
- **Executors** currently provide development/test workloads: `sample`, `failing`, and `flaky`.

### Target architecture

The worker will eventually consume work from Redis Streams and invoke isolated Docker workloads. PostgreSQL will remain the source of truth; Redis will only transport work.

## Execution lifecycle

```text
QUEUED ──► RUNNING ──► SUCCESS
                  └──► FAILED
```

On failure, the worker records the failed Attempt. If attempts remain, it creates the next queued Attempt and returns the JobRun to `QUEUED`. After the third failure, the JobRun becomes `FAILED`.

`CANCELLED`, `TIMED_OUT`, and worker-recovery states are planned, not implemented.

## Quick start

### Prerequisites

- Python 3.12+
- Docker Desktop
- PostgreSQL client dependencies for Python

Create and activate a virtual environment, then install the current runtime and test dependencies:

```bash
python -m venv venv
source venv/bin/activate
python -m pip install fastapi uvicorn sqlalchemy alembic "psycopg[binary]" python-dotenv pytest httpx
```

### Configure local environment

Create local-only configuration from the committed templates:

```bash
cp .env.example .env
cp alembic.ini.example alembic.ini
```

Set the database URL in `.env`:

```text
POSTGRES_URL=postgresql+psycopg://runforge:runforge_dev_password@localhost:5432/runforge
```

`.env` and `alembic.ini` are intentionally ignored by Git. Do not commit credentials.

### Start PostgreSQL and migrate

```bash
docker compose up -d postgres
alembic upgrade head
```

### Start the API

```bash
uvicorn app.api.main:app --reload
```

Interactive API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Start the worker

Run this in a second terminal after activating the same virtual environment:

```bash
python -m app.api.worker.worker
```

The worker polls every three seconds for queued runs.

## API reference

All endpoints are prefixed with `/api`.

### Teams

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/teams` | Create a Team. |
| `POST` | `/teams/bulk` | Create multiple Teams. |
| `GET` | `/teams` | List Teams with `page` and `page_size`. |
| `GET` | `/teams/{team_id}` | Retrieve one Team. |
| `PUT` | `/teams/{team_id}` | Partially update a Team. |
| `DELETE` | `/teams/{team_id}` | Delete a Team when it has no Jobs. |

### Jobs

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/jobs` | Create a Job under a Team. |
| `GET` | `/jobs?team_id={team_id}` | List a Team's Jobs. |
| `GET` | `/jobs/{job_id}` | Retrieve one Job. |
| `PUT` | `/jobs/{job_id}` | Partially update a Job. |
| `DELETE` | `/jobs/{job_id}` | Delete a Job when it has no Runs. |

### Runs and attempts

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/jobs/{job_id}/run` | Create a queued Run and Attempt #1. |
| `GET` | `/jobs/{job_id}/runs` | List Runs; supports `status`, `page`, and `page_size`. |
| `GET` | `/runs/{run_id}` | Retrieve one Run. |
| `DELETE` | `/runs/{run_id}` | Delete a Run and its Attempts. |
| `GET` | `/attempts/{attempt_id}` | Retrieve one Attempt. |
| `GET` | `/runs/{run_id}/attempts` | List a Run's Attempts. |

`POST /runs/{run_id}/cancel` exists as a placeholder only. Cancellation and log retrieval are not implemented.

### Example workflow

```bash
# Create a Team
curl -X POST http://127.0.0.1:8000/api/teams \
  -H 'Content-Type: application/json' \
  -d '{"name":"Platform Engineering","description":"Internal platform workloads"}'

# Create a Job (replace team_id with the Team returned above)
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"team_id":1,"name":"Sample workload","executor_type":"sample","image":"alpine:latest"}'

# Create a queued Run (replace job_id with the Job returned above)
curl -X POST http://127.0.0.1:8000/api/jobs/1/run
```

With the worker running, the sample run will move from `QUEUED` to `SUCCESS`.

## Data integrity and error behavior

- Team names are unique.
- Job names are unique within a Team.
- Attempt numbers are unique and positive within a Run.
- Creating a duplicate resource returns `409 Conflict`.
- Missing resources return `404 Not Found`.
- Invalid request values, including invalid pagination, return `422 Unprocessable Entity`.
- Write operations roll back their database session when a database constraint fails.

## Testing

The test suite uses an isolated in-memory SQLite database with foreign-key enforcement. It covers API behavior, exceptions, worker state transitions, retry behavior, and built-in executors.

```bash
pytest -q
```

## Repository layout

```text
app/
├── api/
│   ├── domain/        # Run and Attempt status enums
│   ├── executors/     # Built-in development/test workloads
│   ├── exceptions/    # Domain errors and HTTP status mapping
│   ├── routes/        # FastAPI endpoints
│   ├── schemas/       # Pydantic request and response models
│   ├── services/      # Business rules and persistence orchestration
│   └── worker/        # Local polling worker
├── db/                # SQLAlchemy engine, sessions, and models
migrations/            # Alembic migration history
tests/                 # API, worker, executor, and exception tests
docker-compose.yaml    # Local PostgreSQL service
```

## Development roadmap

1. Make worker claims and recovery safe under concurrent workers and failures.
2. Add execution timeouts and explicit state-transition rules.
3. Introduce Redis Streams for asynchronous work delivery.
4. Add a Docker executor with output and exit-code capture.
5. Add scheduled runs.
6. Add authentication, Team membership, and role-based access control.
7. Add structured logs, metrics, and traces.
8. Add deployment automation and an evidence-based operations assistant.

## Engineering principles

- Keep PostgreSQL authoritative; queues are delivery mechanisms, not business state.
- Keep route handling, business logic, persistence, worker coordination, and runtime execution separate.
- Make failures explicit: use durable statuses, bounded retries, and deterministic error responses.
- Prefer a small, verified vertical slice over premature infrastructure complexity.
- Never store raw credentials in workload configuration or commit local secrets.
