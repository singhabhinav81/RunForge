# RunForge

**Cross-Team Workload Automation Platform**

RunForge is a backend platform for engineering teams to register, schedule, execute, monitor, and troubleshoot workloads from one place.

The project is being built as a learning-oriented, production-inspired backend system. It starts with a simple API and database, then grows into asynchronous execution, workers, scheduling, reliability, observability, cloud deployment, and eventually an AI operations assistant.

> **Current development principle:** Build one working slice at a time. Understand the design, implement it, test failure cases, and explain why it works before adding the next layer.

---

## Table of contents

- [Why RunForge?](#why-runforge)
- [Core concepts](#core-concepts)
- [Architecture overview](#architecture-overview)
- [Request and execution flows](#request-and-execution-flows)
- [Technology stack](#technology-stack)
- [Project structure](#project-structure)
- [Domain model](#domain-model)
- [API design](#api-design)
- [Execution lifecycle](#execution-lifecycle)
- [Reliability principles](#reliability-principles)
- [Security model](#security-model)
- [Local development](#local-development)
- [Database migrations](#database-migrations)
- [Testing strategy](#testing-strategy)
- [Development roadmap](#development-roadmap)
- [Engineering principles](#engineering-principles)
- [Glossary](#glossary)

---

## Why RunForge?

Engineering teams often run scripts, data extracts, API calls, and other operational workloads in separate cron jobs or ad-hoc processes. That can make execution status, ownership, retries, logs, and troubleshooting difficult to manage consistently.

RunForge aims to provide a shared control plane for those workloads.

### Goals

- Register workloads and associate them with teams.
- Trigger workloads manually and, later, on a schedule.
- Execute work asynchronously instead of keeping HTTP requests open.
- Track every execution and its attempts.
- Support multiple execution types through pluggable executors.
- Add retries, timeouts, concurrency controls, and idempotency.
- Provide access control, logs, metrics, and operational visibility.
- Deploy to cloud infrastructure after the local system is reliable.
- Add an AI operations assistant that explains evidence from the system rather than inventing job status.

### Non-goals for the first version

- Running arbitrary workloads inside the FastAPI process.
- Starting with Kubernetes, AWS, Kafka, and multiple queue technologies at once.
- Building the AI assistant before the execution lifecycle is reliable.
- Implementing every enterprise feature before one end-to-end workload works.

---

## Core concepts

Three concepts must remain separate:

| Concept | Meaning | Example |
|---|---|---|
| **Team** | The engineering group that owns workloads | Data Engineering |
| **Job** | A saved definition describing what should execute | Nightly Jira extract |
| **JobRun** | One specific execution of a Job | Jira extract run on 9 October |
| **Attempt** | One try made to complete a JobRun | Attempt 1 fails; attempt 2 succeeds |

Example:

```text
Team: Data Engineering
└── Job: Jira Extract
    ├── Run #101
    │   ├── Attempt #1: FAILED
    │   └── Attempt #2: SUCCESS
    └── Run #102
        └── Attempt #1: SUCCESS
```

A **Job is not a Run**. The Job stores the definition; each manual or scheduled execution creates a separate JobRun. A retry creates another Attempt under the same JobRun.

---

## Architecture overview

RunForge is designed around a **control plane** and an **execution plane**.

### Control plane

Responsible for defining and managing work.

- FastAPI routes and request validation
- Application services and business rules
- PostgreSQL persistence
- Teams, jobs, schedules, permissions, and execution metadata
- Creating and querying JobRuns
- Authentication and authorization as the security layer develops

### Execution plane

Responsible for doing the work.

- Redis Streams as the work transport
- Workers that consume queued work
- Executors that run a particular workload type
- Docker initially, with HTTP and Kubernetes executors as possible later extensions
- Runtime status updates, output capture, timeout handling, and retries

### Target architecture
```text
                     Client / API Consumer
                              |
                              v
                     +------------------+
                     |     FastAPI      |
                     |   Control Plane  |
                     +--------+---------+
                              |
                              v
                     +------------------+
                     |   PostgreSQL     |
                     | Durable state    |
                     +------------------+

          (when asynchronous execution is introduced)

                     +------------------+
                     |  Redis Streams   |
                     | Work transport   |
                     +--------+---------+
                              |
                              v
                     +------------------+
                     |     Worker       |
                     +--------+---------+
                              |
                              v
                     +------------------+
                     | Executor Factory |
                     +--------+---------+
                              |
                              v
                     +------------------+
                     | Docker Workload  |
                     +------------------+
```

**Important responsibilities:**

- **PostgreSQL is the source of truth.** It stores the authoritative job and execution state.
- **Redis transports work.** It is not a replacement for the database.
- **FastAPI manages requests.** It should not run long-lived workloads directly.
- **The worker performs execution.** It loads the relevant Job and JobRun, selects an executor, runs the workload, and records the result.
- **The executor knows how to run a workload.** The worker should not contain every runtime's implementation details.

The diagram describes the intended architecture. Components are introduced incrementally; not every component is expected to exist in the current codebase.

---

## Request and execution flows

### 1. Create a Team

```text
Client
  -> POST /teams
  -> FastAPI route
  -> Team service
  -> SQLAlchemy model
  -> PostgreSQL
  -> Response
```

The route handles HTTP concerns, the service applies business rules, and the database stores the result.

### 2. Register a Job

```text
Client
  -> POST /jobs
  -> Validate request
  -> Verify the owning Team
  -> Create Job record
  -> PostgreSQL
  -> Return Job response
```

A Job stores configuration. It does not execute anything when created.

### 3. Trigger a Job manually

The intended asynchronous flow is:

```text
Client
  -> POST /jobs/{job_id}/run
  -> FastAPI creates a JobRun
  -> Work is queued
  -> API returns HTTP 202 Accepted with run_id
  -> Worker consumes the message
  -> Worker loads JobRun and Job from PostgreSQL
  -> Executor runs the workload
  -> Worker records the final state
```

The API acknowledges that execution has been accepted; it does not promise that the workload has already finished.

### 4. Scheduled execution

Once the scheduler is implemented:

```text
Scheduler
  -> Find jobs that are due
  -> Create a JobRun
  -> Queue the work
  -> Worker executes it
  -> Persist the outcome
```

The scheduler decides **when** a job should run. It does not execute the workload itself.

---

## Technology stack

| Area | Planned technology | Responsibility |
|---|---|---|
| API | Python, FastAPI, Pydantic | HTTP interface and validation |
| Persistence | PostgreSQL, SQLAlchemy | Durable state and relational data |
| Schema changes | Alembic | Version-controlled database migrations |
| Work queue | Redis Streams | Deliver work to workers |
| Execution | Python worker process | Consume and coordinate work |
| Runtime | Docker initially | Isolate workload processes |
| Scheduling | RunForge scheduler | Determine which jobs are due |
| Tests | pytest | Unit, integration, and end-to-end tests |
| Observability | Prometheus, OpenTelemetry, later log search | Metrics, traces, and operational diagnosis |
| Cloud (later) | AWS, Kubernetes, Terraform, Helm | Production-style deployment and infrastructure |
| AI (later) | LLM API and controlled tool calls | Explain runs and logs using actual system evidence |

Some technologies are future plans, not prerequisites for the first working version.

---

## Project structure

The structure below describes the intended organization. Match it to the actual repository and add modules as they are implemented. Do not create every future file upfront.

```text
RunForge/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── teams.py
│   │   │   ├── jobs.py              # when Job APIs are added
│   │   │   └── runs.py              # when run APIs are added
│   │   ├── schemas/
│   │   │   ├── teams.py
│   │   │   ├── jobs.py
│   │   │   └── runs.py
│   │   ├── services/
│   │   │   ├── teams_service.py
│   │   │   ├── jobs_service.py
│   │   │   └── runs_service.py
│   │   ├── exceptions/
│   │   │   ├── base.py
│   │   │   ├── team.py
│   │   │   ├── job.py
│   │   │   └── run.py
│   │   ├── executors/               # future: Docker, HTTP, Kubernetes
│   │   ├── queue/                   # future: Redis Streams integration
│   │   ├── scheduler/               # future: scheduling logic
│   │   ├── worker/                  # future: worker process
│   │   ├── config/                  # application settings
│   │   └── main.py                  # FastAPI application entry point
│   ├── db/
│   │   ├── database.py              # engine, session factory, Base
│   │   └── models.py                # SQLAlchemy models, or a models package
│   └── ...
├── migrations/                      # Alembic migration versions
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docker/
│   └── ...                          # workload image / Docker assets
├── docs/
│   └── ...                          # architecture and design notes
├── alembic.ini
├── docker-compose.yaml
├── pyproject.toml                   # if used for project configuration
├── requirements.txt                 # if used for dependencies
├── .env.example                     # safe template, no real secrets
└── README.md
```

### What belongs where?

| Location | Responsibility |
|---|---|
| `routes/` | HTTP endpoints, status codes, dependency wiring |
| `schemas/` | Pydantic request and response contracts |
| `services/` | Business rules and orchestration |
| `exceptions/` | Application/domain errors |
| `db/` | SQLAlchemy engine, sessions, and models |
| `queue/` | Publishing and consuming queue messages |
| `worker/` | Claiming and coordinating execution |
| `executors/` | Runtime-specific execution implementations |
| `scheduler/` | Finding work that is due |
| `migrations/` | Database schema history |
| `tests/` | Tests grouped by scope |

**Keep one owner for database setup.** For example, use `app/db/database.py` for the engine and session factory instead of maintaining duplicate database modules in multiple folders.

The current repository may not contain all folders listed above. They are planned destinations, not a requirement to scaffold everything now. If the existing project uses `app/api/db/deps.py` for FastAPI database dependencies, that can remain, provided engine/session ownership is not duplicated.

---

## Domain model

### Team

A Team owns Jobs. Users may belong to teams through membership records.

Potential fields:

```text
Team
----
id
name
description
created_at
updated_at
```

### Job

A Job defines the workload and its execution configuration.

Initial fields may include:

```text
Job
---
id
team_id
name
description
executor_type
image
created_at
updated_at
```

The exact configuration will evolve. Avoid adding every retry, schedule, resource, and secret field before the related feature is implemented.

### JobRun

A JobRun records one requested or scheduled execution.

```text
JobRun
------
id
job_id
status
created_at
started_at
finished_at
```

### Attempt

An Attempt records one try for a JobRun.

```text
JobAttempt
----------
id
run_id
attempt_number
status
started_at
finished_at
error
```

These are conceptual starting points. Add fields and constraints based on real lifecycle requirements, and create schema changes through Alembic migrations.

---

## API design

Initial Team endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/teams` | Create a Team |
| `GET` | `/teams` | List Teams, with pagination |
| `GET` | `/teams/{team_id}` | Get one Team |
| `PUT` | `/teams/{team_id}` | Update a Team |
| `DELETE` | `/teams/{team_id}` | Delete or archive a Team, according to the chosen policy |

Planned Job endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/jobs` | Register a Job |
| `GET` | `/jobs` | List Jobs |
| `GET` | `/jobs/{job_id}` | Get one Job |
| `PUT` | `/jobs/{job_id}` | Update a Job |
| `DELETE` | `/jobs/{job_id}` | Delete or archive a Job |

Planned execution endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/jobs/{job_id}/run` | Request a new run |
| `GET` | `/jobs/{job_id}/runs` | List runs for a Job |
| `GET` | `/runs/{run_id}` | Inspect a run |
| `POST` | `/runs/{run_id}/cancel` | Request cancellation, when supported |
| `GET` | `/runs/{run_id}/logs` | Retrieve run logs, when log storage exists |

These are planned API contracts. Confirm request/response fields and behavior as each endpoint is implemented.

### API conventions

- Use separate Pydantic schemas for create/update requests and responses.
- Do not ask clients to provide database-managed timestamps or IDs unless the API specifically requires them.
- Validate input at the API boundary.
- Keep business rules in services rather than duplicating them in route handlers.
- Use meaningful HTTP status codes, such as `201 Created`, `202 Accepted`, `404 Not Found`, and `409 Conflict`.
- Return consistent error responses.
- Never return password hashes or secret values.

---

## Execution lifecycle

A basic JobRun lifecycle may begin as:

```text
QUEUED -> RUNNING -> SUCCESS
                   \-> FAILED
```

Additional states can be introduced when the behavior is implemented, such as `CANCELLED`, `TIMED_OUT`, or `LOST`.

Treat status changes as state transitions with rules, not arbitrary string assignments. For example, a completed run should not silently transition back to `RUNNING`.

Retries should create new Attempts under the same JobRun rather than pretending each retry is a brand-new user-requested run.

---

## Reliability principles

These are important design goals, introduced in stages.

### Durable state

PostgreSQL stores authoritative Job and JobRun state.

### Idempotency

Repeated delivery of the same work message should not accidentally create multiple executions for the same logical request. A scheduled-run uniqueness rule may eventually use a key such as `(job_id, scheduled_time)`, where appropriate.

### Retries

Retry transient failures according to an explicit policy, potentially using exponential backoff. Avoid infinite retry loops.

### Timeouts

A workload should not be allowed to run indefinitely. Timeout behavior must include how the process is stopped and how the final state is recorded.

### Worker recovery

If a worker disappears while a run is marked `RUNNING`, the system needs a way to detect and recover or mark the run appropriately.

### Delivery guarantees

A queue can redeliver work. Design the worker and state transitions with that possibility in mind; do not assume every message is delivered exactly once.

### Transactional consistency

A database commit and queue publish are separate operations. Later, a transactional outbox can help avoid a run being committed to PostgreSQL without its queue message being published. Introduce it when the basic flow works and the failure window is understood.

---

## Security model

Security will be introduced incrementally.

- **Authentication** answers: who is making the request?
- **Authorization** answers: what is that identity allowed to do?
- Jobs belong to Teams, while `created_by` can record who registered them.
- Team membership and roles can control access to Jobs and Runs.
- Never store raw credentials in Job configuration.
- Store references to secrets and resolve them securely at runtime.
- Use environment-based configuration for local development and keep real `.env` files out of version control.
- Add production-grade identity integration, such as OIDC/SSO, when the system is ready.

Possible roles include Admin, Operator, Developer, and Viewer. Their precise permissions must be defined before enforcement.

---

## Local development

The exact commands depend on the repository's current dependency and Compose configuration. Check `docker-compose.yaml`, `pyproject.toml` or `requirements.txt`, and `alembic.ini` before running commands.

### 1. Prepare environment variables

Create a local `.env` file from `.env.example` if the application is configured to load one. Never commit credentials.

### 2. Start dependencies

If the Compose file defines PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
```

If service names differ, use the names defined in your Compose file.

### 3. Apply database migrations

```bash
alembic upgrade head
```

### 4. Start the API

Use the application import path that exists in the repository. For example, if the FastAPI instance is `app.api.main:app`:

```bash
uvicorn app.api.main:app --reload
```

If `main.py` is at `app/main.py`, the import path will be different.

### 5. Explore the API

FastAPI's interactive documentation is usually available at:

```text
/docs
```

The complete local URL depends on the configured host and port, commonly `http://127.0.0.1:8000/docs`.

**Important:** These are common example commands, not a claim that every service or script is already configured. Confirm them against the repository.

---

## Database migrations

Use Alembic to track schema changes.

Typical workflow:

```bash
# Generate a candidate migration
alembic revision --autogenerate -m "describe schema change"

# Inspect the generated migration before applying it
# Then apply migrations
alembic upgrade head

# Check the current revision
alembic current

# View migration history
alembic history
```

Autogenerated migrations are drafts, not guaranteed-correct changes. Inspect constraints, nullability, defaults, foreign keys, indexes, and data backfills before applying them, especially on existing data.

Avoid using `Base.metadata.create_all()` as a replacement for the migration workflow once Alembic owns schema changes.

---

## Testing strategy

Test each layer at the appropriate level.

### Unit tests

Test isolated business behavior:

- Duplicate Team detection
- Missing Team behavior
- Pagination validation
- JobRun state-transition rules
- Retry-delay calculation, when implemented

### Integration tests

Test interactions with real or test instances of dependencies:

- API plus PostgreSQL
- Database constraints and relationships
- Queue publishing and consuming, once Redis is introduced

### End-to-end test

The long-term smoke test is:

```text
Create Job
   -> Request JobRun
   -> Queue message
   -> Worker consumes message
   -> Executor runs a test workload
   -> JobRun becomes SUCCESS
```

Also test failure paths. A system that only works when nothing goes wrong is still a prototype.

---

## Development roadmap

Build in this order. Do not treat future phases as completed features.

1. **Team APIs:** complete create, read, list, update, delete/archive behavior.
2. **Application exceptions:** define useful domain errors and map them consistently to HTTP responses.
3. **Job domain:** model, schemas, service, and CRUD endpoints.
4. **JobRun domain:** create a run record and define allowed state transitions.
5. **Attempts:** record individual execution tries.
6. **Redis Streams:** queue work for asynchronous processing.
7. **Worker:** consume messages and coordinate execution.
8. **Docker Executor:** execute a safe test workload and capture exit status/output.
9. **Reliability:** retries, timeouts, idempotency, and worker recovery.
10. **Scheduler:** create runs for due jobs.
11. **Security:** authentication, team membership, and RBAC.
12. **Logs and observability:** structured logs, metrics, and traces.
13. **Cloud deployment:** Docker images, AWS, Kubernetes, Terraform, Helm, and CI/CD.
14. **AI operations assistant:** answer operational questions using controlled tools and actual job/run/log data.

### The development loop

For each feature, follow:

**Problem -> Design -> Build -> Break -> Fix -> Explain**

Before coding, answer:

1. What problem does this feature solve?
2. Which component owns the responsibility?
3. What data needs to be stored?
4. What happens on invalid input or failure?
5. How will it be tested?
6. Can you explain the code and its trade-offs?

Use AI for review, debugging, boilerplate, and alternative designs. Make sure you understand the important business logic before accepting generated code.

---

## Engineering principles

1. **Keep responsibilities separate.** Routes handle HTTP, services handle business rules, models represent persistence, workers coordinate execution, and executors run workloads.
2. **Start with one vertical slice.** Make one workload run successfully before adding several infrastructure systems.
3. **Prefer explicit behavior.** Define status transitions, retry policy, timeout behavior, and deletion policy.
4. **Design for failures.** Messages may be redelivered, workers may crash, and external workloads may fail.
5. **Avoid premature abstraction.** Add interfaces when they solve a real problem, not merely to create more files.
6. **Keep PostgreSQL authoritative.** Queue messages are delivery mechanisms, not the durable business record.
7. **Use migrations.** Keep database schema changes reviewable and reproducible.
8. **Protect secrets.** Store references, not plaintext credentials.
9. **Test the unhappy path.** Missing records, duplicates, invalid state changes, and dependency failures deserve tests.
10. **Build understanding, not just output.** The project is successful when you can explain why it works and how it fails.

---

## Glossary

| Term | Meaning |
|---|---|
| **Control plane** | The API and services that manage workload definitions and execution metadata |
| **Execution plane** | The workers and executors that perform workloads |
| **Job** | A stored workload definition |
| **JobRun** | One requested or scheduled execution of a Job |
| **Attempt** | One try to complete a JobRun |
| **Worker** | A process that consumes queued work and coordinates execution |
| **Executor** | A component that knows how to run a workload using a specific runtime |
| **Scheduler** | A component that determines when scheduled work is due |
| **Redis Stream** | A Redis data structure used to transport messages to consumers |
| **Idempotency** | Repeating an operation does not create an unintended duplicate effect |
| **RBAC** | Role-Based Access Control |
| **Transactional outbox** | A pattern for reliably publishing events associated with a database transaction |
| **DAG** | Directed Acyclic Graph, useful for representing dependent tasks or workflows |

---

## Current focus

**Finish the Team API and exception handling, then build the Job domain.**

Do not start the Redis worker, scheduler, Kubernetes, or AI assistant until the current layer is understood and tested.

RunForge should grow from a small, correct backend into a reliable workload platform, one verified capability at a time.
