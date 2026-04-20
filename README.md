# Remindam Bot Backend

Internal repository for the Remindam WhatsApp bot backend service.

## Architecture

* **API Layer:** FastAPI (handles webhooks, user endpoints, Paystack webhooks)
* **Messaging integration:** Twilio WhatsApp API
* **Task Queue:** Celery with Redis broker
* **Database:** PostgreSQL (Async) + SQLAlchemy + Alembic
* **Environment:** `uv` for dependency management

## Local Development

### Prerequisites
* Python 3.12
* PostgreSQL
* Redis (local or remote)
* `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Setup

1. Install dependencies:
   ```sh
   uv sync --all-extras
   ```

2. Environment Variables:
   Copy `.env.example` to `.env` and fill in the required internal keys (Twilio, Paystack, JWT secret).
   Ensure `DATABASE_URL` matches your local Postgres credentials.

3. Database Migrations:
   ```sh
   uv run alembic upgrade head
   ```

### Running Locally

You need to run the API, the Celery worker, and the scheduler concurrently.

```sh
# Terminal 1 - API
uv run uvicorn app.main:app --reload

# Terminal 2 - Task Worker
uv run celery -A app.scheduler worker --loglevel=info

# Terminal 3 - CRON Scheduler
uv run celery -A app.scheduler beat --loglevel=info
```

*To receive Twilio webhooks locally, expose port 8000 using Ngrok (`ngrok http 8000`) and set your NGrok URL as `BASE_URL` in `.env` and Twilio.*

## Deployment (Coolify)

This service is deployed via **Coolify** using a multi-container Docker Compose setup.

### Services (`docker-compose.yml`)
* `web` (FastAPI server)
* `worker` (Celery background tasks)
* `beat` (Celery scheduler for periodic reminders)
* `db` (Postgres 16)
* `redis` (Redis 7)

### Coolify Configuration
1. Point a new Coolify Docker Compose project to this repository.
2. The `entrypoint.sh` automatically runs Alembic migrations on deployment before starting the web server.
3. **Environment Variables required in Coolify:**
   * `POSTGRES_PASSWORD` (Internal DB password)
   * `BASE_URL` (The public domain mapping to the app)
   * App secrets (`TWILIO_*`, `PAYSTACK_*`, etc.)
   * *(Note: `DATABASE_URL` and `REDIS_URL` are auto-mapped internally by Compose).*

## Contributing
* We use `ruff` for linting. Install hooks via `uv run pre-commit install`.
* Create migrations for all DB model changes via `uv run alembic revision --autogenerate -m "msg"`.
* Ensure tests pass before pushing (`uv run pytest`).
