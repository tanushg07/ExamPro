# EXAMPRO

An online examination platform built with Flask that supports role-based workflows for admins, teachers, and students, including exam creation, timed attempts, grading, analytics, notifications, and anti-cheat event tracking.

## Why This Project Exists

Most exam systems are either too rigid or too risky.
ExamPro is designed to be practical for real classrooms while still enforcing exam integrity.

- Teachers can create, publish, review, and export exams.
- Students can take timed exams and view results and reviews.
- Admins can manage users, exams, settings, and system activity.
- The app tracks security signals during attempts (focus loss, window switches, verification status, and more).

## Feature Blast

### Role-Based Experience

- Admin panel for user and exam lifecycle operations.
- Teacher dashboard with exam authoring, grading queue, analytics, gradebook, and exports.
- Student dashboard for exam attempts, result viewing, and reviews.

### Exam Authoring and Delivery

- MCQ and text/code-style question support.
- Publish/unpublish workflow.
- Availability windows (`available_from`, `available_until`).
- Optional randomization and one-question-at-a-time delivery.

### Security and Integrity Controls

- Attempt-level fields for browser fingerprint, IP, user agent, screen data, warnings, and verification status.
- Event payload storage for browser/security warning streams.
- Submission metadata support (submission IP, location, timezone).

### Data and Operations

- SQLAlchemy models with relationships and indexes for exam and grading workloads.
- Background task scheduler integration for notifications.
- Docker support and GitHub Actions CI pipeline.

## Tech Stack

- Python 3.11
- Flask + Flask extensions (Login, WTForms, Migrate, Mail)
- SQLAlchemy ORM
- MySQL (CI) and SQLite (default local)
- Pytest + Flake8 + Docker

Main dependencies are defined in `requirements.txt`.

## Project Structure

```text
ExamPro/
	app.py                     # Application entrypoint
	config.py                  # Runtime configuration
	app/
		__init__.py              # App factory, extension wiring, blueprint registration
		models.py                # Core domain models
		auth.py                  # Authentication routes
		routes.py                # Main, teacher, and student routes
		admin_routes.py          # Admin routes
		group_routes.py          # Group management routes
		background_tasks.py      # Scheduler/task registration
	templates/                 # Jinja templates
	static/                    # CSS/JS/assets
	tests/                     # Test suite
	.github/workflows/ci.yml   # CI workflow
```

## Quick Start (Local)

### 1) Create and activate a virtual environment

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Bash:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3) Configure environment variables

Set these minimum values:

- `SECRET_KEY` (required)
- `DATABASE_URL` (optional for local; defaults to SQLite)

Examples:

SQLite (default local behavior in `config.py`):

```env
SECRET_KEY=dev-secret-change-me
DATABASE_URL=sqlite:///exampro_dev.db
```

MySQL:

```env
SECRET_KEY=dev-secret-change-me
DATABASE_URL=mysql+mysqlconnector://exam_user:exam_pass@127.0.0.1/exam_platform
```

### 4) Run the app

```bash
python app.py
```

Server starts on:

- http://127.0.0.1:5000

## Run With Docker

```bash
docker compose up --build
```

The default compose setup runs the Flask app with:

- Port `5000:5000`
- SQLite database file mounted via `./instance`

## Database Notes

- Local default database is SQLite (`sqlite:///exampro_dev.db` when `DATABASE_URL` is not set).
- CI uses MySQL 8 service and a dedicated test DB.
- App startup includes connectivity checks and may create missing tables during boot.

## Testing and Quality

Run tests:

```bash
pytest -q tests
```

Run lint gate used by CI:

```bash
flake8 app.py app --exclude=*_backup.py,backup_* --count --select=E9,F63,F7,F82 --show-source --statistics
```

## CI Workflow

The GitHub Actions workflow in `.github/workflows/ci.yml` performs:

1. Python setup
2. Dependency install
3. MySQL service readiness and DB prep
4. Lint checks
5. App smoke check (`create_app()` import + initialization)
6. Pytest suite execution
7. Docker image build

## Security-Centric Data Model Highlights

From `app/models.py`, `ExamAttempt` includes fields for:

- `browser_fingerprint`
- `ip_address`
- `warning_count`
- `security_events`
- `verification_status`
- `server_side_checks`

This is central to auditability and suspicious-behavior analysis.

## Common Commands

Install deps:

```bash
pip install -r requirements.txt
```

Run app:

```bash
python app.py
```

Run tests:

```bash
pytest -q tests
```

Build image:

```bash
docker build -t exampro:latest .
```

## Troubleshooting

### App fails to start

- Verify `SECRET_KEY` is present.
- Verify DB URL format and database availability.
- Check startup output from `app.py` for connection errors.

### Tests fail in local environment

- Ensure dependencies are installed in the active virtual environment.
- Ensure no stale DB state conflicts with test expectations.
- Re-run with verbose output:

```bash
pytest -vv tests
```

### Docker health checks fail

- Confirm container logs:

```bash
docker compose logs -f web
```

- Confirm port `5000` is free locally.

## Contributing

1. Create a feature branch.
2. Keep changes scoped and test-backed.
3. Run lint + tests before opening a PR.
4. Ensure CI passes.

## License

No license file is currently declared in this repository.

---

If you wanted a "crazy" README update, mission accomplished: this one is fast to scan, complete enough to onboard a teammate, and aligned with your real code and CI behavior.