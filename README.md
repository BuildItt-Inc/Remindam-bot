# WhatsApp Medication Reminder Bot (Remindam)

A reliable, NDPR-compliant WhatsApp bot that helps users remember their medication schedules via scheduled Twilio messages.

## Tech Stack
* **Framework:** FastAPI
* **Database:** PostgreSQL (Async) + SQLAlchemy + Alembic
* **Task Queue:** Celery + Celery Beat + Redis
* **Messaging:** Twilio API
* **Package Manager:** [uv](https://docs.astral.sh/uv/)

---

## 🚀 Quick Setup Guide

### 1. Prerequisites
Ensure you have the following installed on your machine:
* Python `3.12+`
* PostgreSQL
* Redis (running locally on port 6379 or update `.env` accordingly)
* [uv package manager](https://docs.astral.sh/uv/getting-started/installation/)

  **Linux/macOS:**
```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
```
  **Windows:**
```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone and Setup Environment
Clone the repository and install all dependencies (including dev tools and pre-commit hooks) using `uv`.

```sh
# Clone repo
git clone <your-repo-url>
cd Remindam-bot

# Install dependencies and sync virtual environment
uv sync --all-extras
```

### 3. Environment Variables
Create a `.env` file in the root directory and copy these variables:

```env
# Database configuration
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/remindam

# Redis configuration
REDIS_URL=redis://localhost:6379/0

# Security (JWT)
JWT_SECRET_KEY=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Subscription configuration
TRIAL_DAYS=3
GRACE_DAYS=2
```
> **Note:** Update the `DATABASE_URL` username, password, and port to match your local PostgreSQL setup. Make sure the database actually exists! (e.g., `createdb remindam`).

### 4. Database Setup & Migrations
We use Alembic for database migrations. To apply the initial schema to your database:

First, create the local database:
```sh
createdb remindam
```
> If `createdb` fails, try: `sudo -u postgres psql -c "CREATE DATABASE remindam;"`

Then apply migrations:
```sh
uv run alembic upgrade head
```

### 5. Running the Application

You'll need three terminal tabs to run the full stack locally:

**Tab 1: Start the FastAPI Server**
```sh
uv run uvicorn app.main:app --reload
```
*API documentation will be available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).*

**Tab 2: Start the Celery Worker (Task execution)**
```sh
uv run celery -A app.scheduler worker --loglevel=info
```

**Tab 3: Start Celery Beat (Scheduled tasks)**
```sh
uv run celery -A app.scheduler beat --loglevel=info
```

---

## 🛠 Development Workflow

### Pre-commit Hooks
This project uses `pre-commit` to ensure code formatting and linting standards are maintained automatically.

If you haven't installed the git hooks yet, run:
```sh
uv run pre-commit install
```
This will automatically format your code via `Ruff` whenever you run `git commit`. You can also format everything manually with:
```sh
uv run pre-commit run --all-files
```

If you prefer to run formatting manually without pre-commit:
```sh
uv run ruff format .
uv run ruff check . --fix
```

### Database Migrations
Whenever you change a SQLAlchemy model in `app/models/`:

1. **Auto-generate a new migration:**
   ```sh
   uv run alembic revision --autogenerate -m "describe the change"
   ```
2. **Apply migration to your local database:**
   ```sh
   uv run alembic upgrade head
   ```

### Running Tests
We use Pytest. Run the full test suite with:
```sh
uv run pytest tests/ --verbose
```

## Review Guidelines
Before opening a PR, always refer to our standard [CONTRIBUTING.md](./CONTRIBUTING.md). Include your ticket number in your branch name (e.g. `feat/RBD-42-some-feature`) and follow conventional commit formats.
