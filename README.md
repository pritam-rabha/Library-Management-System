# Library Management System

A Flask-based web application for managing a small library. It supports book and member records, book issuing and returning, automatic overdue fines, search and filtering, transaction history, and validated backup and restore. Runtime data is stored in a JSON file.

## Live Demo

**Live Application:** [Library Management System](https://library-management-system-pmko.onrender.com)

> **Deployment note:** The live demo is hosted on Render Free, where the filesystem is ephemeral. Data created during a session may be lost after a restart or redeployment. See [Data persistence](#data-persistence).

## Project Information

| Field | Details |
|---|---|
| Application | [Library Management System](https://library-management-system-pmko.onrender.com) |
| Author | Pritam Rabha |
| Programme | MCA, 3rd Semester |
| Course | Python Programming |
| Project Guide | Dr. Pangambam Sendash Singh |
| Institution | Dr. Hari Singh Gour Vishwavidyalaya, Sagar, Madhya Pradesh |
| Copyright | Copyright © 2026 Pritam Rabha. All rights reserved. |

> **Academic disclaimer:** This is an independent educational project prepared for an MCA Python Programming assignment. It is not an official application of Dr. Hari Singh Gour Vishwavidyalaya, Sagar, and the university has not reviewed or endorsed it. All books, members, and loan records in the sample data are fictional.

## Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Technology stack](#technology-stack)
4. [Project structure](#project-structure)
5. [Requirements](#requirements)
6. [Local installation](#local-installation)
7. [Administrator setup](#administrator-setup)
8. [Run the application](#run-the-application)
9. [Using the application](#using-the-application)
10. [Configuration](#configuration)
11. [Scoring and fine calculation](#fine-calculation)
12. [Testing](#testing)
13. [Deployment on Render](#deployment-on-render)
14. [Data persistence](#data-persistence)
15. [Security considerations](#security-considerations)
16. [Troubleshooting](#troubleshooting)
17. [Limitations and future improvements](#limitations-and-future-improvements)
18. [Credits and copyright](#credits-and-copyright)

## Overview

The Library Management System helps manage everyday library operations through a web interface. Administrators can maintain book and member records, issue available books, record returns, calculate overdue fines, search the catalogue, review circulation history, and back up or restore library data.

The application is built with Python and Flask. It uses JSON file storage rather than a database, so the runtime data file and deployment environment should be considered when using the application.

## Features

| Feature | Description |
|---|---|
| Book management | Add, view, edit, and delete book records with input validation and duplicate protection. |
| Member management | Add, view, edit, and delete members. Members with books currently on loan cannot be deleted. |
| Book issuing and returns | Record issue and due dates, track available copies, record returns, and prevent issuing a title when no copies remain. |
| Loan restrictions | Prevent a member from holding two copies of the same title and enforce the configured loan limit per member. |
| Automatic overdue fines | Calculate fines using overdue days and the configured daily rate. Store the final fine when a book is returned. |
| Search and filters | Search titles and authors using case-insensitive, partial, multi-word matching; filter by category and availability. |
| Available and issued books | View copy counts, borrowers, issue dates, due dates, overdue status, and running fines. |
| Transaction history | Review previous circulation transactions. |
| Dashboard | View total books, available copies, issued books, registered members, overdue books, and recent activity. |
| Backup and restore | Download a JSON backup with a SHA-256 checksum. Validate and preview a restore before confirming it. |
| Settings | Configure the daily fine rate, standard loan period, and maximum loans per member. |
| Security controls | Includes administrator authentication, password hashing, CSRF protection, login throttling, and security headers as implemented. |
| Automated tests | Includes a pytest suite covering core functionality, validation, storage, and security. |
| Responsive web interface | Uses Flask templates, Bootstrap, and JavaScript for the web interface. |

## Technology stack

- **Language:** Python 3.11+
- **Web framework:** Flask
- **Templating:** Jinja
- **Frontend:** HTML, CSS, Bootstrap 5.3, JavaScript
- **Storage:** JSON file
- **Testing:** pytest
- **Production server:** Gunicorn
- **Deployment configuration:** Render Blueprint (`render.yaml`)

Bootstrap is loaded from a CDN, so the interface requires an internet connection to load Bootstrap assets unless they are hosted locally.

## Project structure

```text
Library_Management_System/
├── app/
│   ├── __init__.py                  # Application factory and error handlers
│   ├── config.py                    # Environment-based configuration
│   ├── security.py                  # Login guard and security controls
│   ├── storage.py                   # JSON storage and atomic writes
│   ├── routes/                      # Authentication, books, members, circulation, backup
│   ├── services/                    # Business logic and validation
│   ├── templates/                   # Jinja templates
│   └── static/
│       ├── css/style.css
│       ├── js/app.js
│       └── images/dhsgu-logo.png
├── data/
│   ├── sample/
│   │   └── sample_data.json         # Fictional sample records
│   └── runtime/
│       └── library.json             # Runtime data; should not be committed
├── scripts/
│   └── generate_credentials.py      # Generates credentials and secret key
├── tests/                           # pytest suite
├── wsgi.py                          # WSGI entry point
├── render.yaml                      # Render deployment blueprint
├── requirements.txt                 # Runtime dependencies
├── requirements-dev.txt             # Runtime and test dependencies
├── pytest.ini
├── .env.example                     # Example environment configuration
├── .gitignore
└── README.md
```

The application reads sample data from `data/sample/sample_data.json` and can use it to initialise `data/runtime/library.json` on first start when `SEED_SAMPLE_DATA=true`. Sample loan dates are relative, so some loans may be overdue when the project is first run. Set `SEED_SAMPLE_DATA=false` to initialise an empty library.

## Requirements

- Python 3.11 or newer
- `pip`
- A terminal or command prompt
- Git (optional, but useful for version control and deployment)

Check your Python version:

```bash
python3 --version
```

## Local installation

The following steps are for Ubuntu or another Linux distribution with Python 3.11+ installed.

### 1. Extract or open the project

If you downloaded the project as a ZIP file:

```bash
unzip Library_Management_System.zip
cd Library_Management_System
```

If the project folder already exists, change to that directory instead.

### 2. Install Python tools and create a virtual environment

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 3. Configure environment variables

Create a local environment file:

```bash
cp .env.example .env
```

Generate a secret key:

```bash
python scripts/generate_credentials.py --secret
```

Copy the generated value into `SECRET_KEY` in `.env`. Then generate an administrator password hash:

```bash
python scripts/generate_credentials.py
```

Follow the prompt and copy the generated hash into `ADMIN_PASSWORD_HASH`. Edit the configuration file:

```bash
nano .env
```

Set `ADMIN_USERNAME`, `SECRET_KEY`, and `ADMIN_PASSWORD_HASH`. Keep `.env` private and never commit it to Git.

## Administrator setup

Administrator login is enabled when the required credentials are configured.

1. Generate a secret key using `python scripts/generate_credentials.py --secret`.
2. Generate a password hash using `python scripts/generate_credentials.py`.
3. Put the values in `.env` as `SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD_HASH`.
4. Start the application and sign in with the configured username and the password used to generate the hash.

The password itself is not stored in the application configuration; the configured value is a password hash. Do not share credentials or commit them to the repository.

## Run the application

### Development server

With the virtual environment activated and `.env` configured, run:

```bash
flask --app wsgi run --debug
```

Open the application at:

- **Local application:** <http://127.0.0.1:5000>

### Production-style local server

For a local production-style run, use a single Gunicorn worker:

```bash
gunicorn wsgi:app --workers 1 --threads 4 --bind 127.0.0.1:8000
```

Then open <http://127.0.0.1:8000>.

> **Important:** Use a single Gunicorn worker with the current JSON storage implementation. The JSON store serialises writes within one process; multiple worker processes writing to the same file could overwrite one another's changes.

## Using the application

1. **Dashboard:** Review headline statistics, overdue loans, and recent activity.
2. **Books:** View the catalogue and add, edit, or delete book records.
3. **Members:** Manage registered library members.
4. **Issue a book:** Select an available book and a member. The due date is based on the configured loan period or the period entered.
5. **Issued books:** Review borrowers and due dates. Overdue loans are labelled and show the running fine. Use the return action to record a return and final fine.
6. **Search:** Search by book title or author and use category and availability filters.
7. **Backup and restore:** Download a backup when needed. To restore, select a file, choose **Check file**, review the validation summary, tick the confirmation box, and confirm. The existing data is backed up before replacement.
8. **Settings:** Change the daily fine rate, standard loan period, and maximum loans per member.

## Configuration

Use `.env.example` and `app/config.py` as the authoritative references for supported settings.

| Variable | Purpose | Default or notes |
|---|---|---|
| `APP_ENV` | Selects development or production mode. Production mode requires a secret key and enables secure-cookie and HSTS settings. | `development` |
| `SECRET_KEY` | Signs session cookies. | Random per start in development; required in production |
| `ADMIN_USERNAME` | Administrator username. | Unset means administrator login is disabled |
| `ADMIN_PASSWORD_HASH` | Hash generated by `scripts/generate_credentials.py`. | Unset means administrator login is disabled |
| `FINE_PER_DAY` | Initial daily fine rate when the data file is created. | `2.00` |
| `LOAN_DAYS` | Initial standard loan period in days. | `14` |
| `MAX_LOANS_PER_MEMBER` | Initial maximum loans per member. | `5` |
| `CURRENCY_SYMBOL` | Currency symbol displayed with fines. | Rupee sign |
| `TIMEZONE` | Time zone used to determine the current date. | `Asia/Kolkata` |
| `SEED_SAMPLE_DATA` | Whether sample data is loaded on first start. | `true` |
| `DATA_FILE` | Location of the runtime JSON file. | `data/runtime/library.json` |
| `SESSION_MINUTES` | Idle session lifetime. | `30` |
| `LOGIN_MAX_ATTEMPTS` | Failed-login attempts before lockout. | `5` |
| `LOGIN_LOCK_SECONDS` | Lockout duration after failed login attempts. | `300` |

The fine rate, loan period, and loan limit are initial values when the runtime data file is first created. After initialisation, change these values through the Settings page where supported.

## Fine calculation

The application calculates an overdue fine using the following formula:

**Fine = Overdue days × Fine per day**

The daily fine rate is configurable. For books still on loan, the application displays overdue days and the running fine. When a book is returned, the final fine is recorded with the return.

The configured time zone is used to determine the current date. If dates appear to be one day out, check the `TIMEZONE` setting.

## Testing

Activate the virtual environment and run the test suite:

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

To run tests with more detail:

```bash
pytest -v
```

The test suite covers the application's mandatory features, including invalid inputs, duplicate IDs and ISBNs, unavailable books, overdue fines, backup and restore, authentication, and storage behaviour.

| Test file | Coverage |
|---|---|
| `test_circulation.py` | Issue and return flows, dates, available copies, unavailable books, and loan limits |
| `test_fines.py` | Fine formula, configurable rate, overdue days, and settings validation |
| `test_search.py` | Title and author search, case handling, partial words, empty results, and filters |
| `test_books_members.py` | CRUD operations, validation, duplicates, and deletion protection |
| `test_listings.py` | Available and issued lists, overdue highlighting, and dashboard figures |
| `test_backup.py` | Export, restore, confirmation, and invalid or inconsistent backup files |
| `test_security.py` | Login, logout, CSRF, throttling, headers, cookies, and escaping |
| `test_storage.py` | Atomic writes, failed writes, corrupted data, and sample-data separation |

## Deployment on Render

The repository includes a `render.yaml` Blueprint configuration.

### Blueprint deployment

1. Push the project to GitHub.
2. Sign in to [Render](https://render.com).
3. Choose **New → Blueprint**.
4. Connect the GitHub repository and select it.
5. Review the settings detected from `render.yaml`.
6. Provide the required administrator credentials when prompted.
7. Deploy and inspect the build and runtime logs.

Generate the administrator password hash locally with:

```bash
python scripts/generate_credentials.py
```

Enter the full hash as `ADMIN_PASSWORD_HASH` and set `ADMIN_USERNAME` as requested by the deployment configuration. The supplied configuration generates `SECRET_KEY` automatically on Render.

### Manual web service

If you create the service manually, use the following settings only if they match the repository's current configuration.

**Build command**

```bash
pip install -r requirements.txt
```

**Start command**

```bash
gunicorn wsgi:app --workers 1 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT
```

**Health-check path**

```text
/healthz
```

After deployment, open the Render URL and sign in with the administrator credentials configured for the service.

## Data persistence

The application stores runtime records in a JSON file, normally `data/runtime/library.json`. Render Free web services use an ephemeral filesystem, so runtime changes may be lost when the service restarts, redeploys, or starts again after idling.

To reduce the risk of losing data:

- Download a backup from **Backup and restore** before ending a session.
- Run the application locally for records that must be retained.
- For persistent hosted data, use an appropriate persistent-storage option or migrate to a managed database.

The application may reinitialise from sample data after a restart if sample seeding is enabled. This does not guarantee recovery of user-created records or transactions.

## Security considerations

The application includes the following controls as described by the project:

- Administrator passwords are stored as salted PBKDF2-SHA256 hashes.
- State-changing requests require CSRF protection; logout uses a POST request.
- Session cookies use `HttpOnly` and `SameSite=Lax`, and are configured as `Secure` in production.
- Sessions are replaced at login and expire after inactivity.
- Repeated failed logins are temporarily blocked.
- Login redirect targets are restricted to local paths.
- Responses include security headers such as Content-Security-Policy, `X-Frame-Options: DENY`, `nosniff`, and `no-store`.
- User-provided text is escaped by Jinja.
- Backup files are size-limited, parsed as JSON, checksum-verified, and validated before they can be restored.

The SHA-256 checksum detects accidental damage or changes; it is not a digital signature. Restore only backup files you trust.

Bootstrap is loaded from a CDN without a Subresource Integrity attribute. For a stricter deployment, host Bootstrap locally and update the stylesheet reference in `base.html`. Review the actual code and production configuration before relying on any security control.

## Troubleshooting

| Problem | Possible solution |
|---|---|
| Administrator credentials are not configured | Set `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` in `.env` or the hosting environment, then restart the application. |
| Application exits because `SECRET_KEY` is missing | Production mode requires `SECRET_KEY`. Generate one with `python scripts/generate_credentials.py --secret`. |
| Runtime data file is corrupted | Restore a trusted backup or use the available backup file if present. The application is designed not to overwrite a file it cannot read. |
| Pages have no styling while offline | Bootstrap is loaded from a CDN and needs internet access unless hosted locally. |
| Dates appear to be off by one day | Check the `TIMEZONE` setting; for India, use `Asia/Kolkata`. |
| Data disappears after deployment | Check whether the hosting platform uses ephemeral storage. Download a backup or configure persistent storage. |
| Deployment fails | Review Render build and runtime logs. Verify the Python version, dependencies, start command, environment variables, health-check path, and `render.yaml`. |
| Changes to settings do not match environment values | Some settings are initial values used when the runtime data file is first created. Check the Settings page for current stored values. |

## Limitations and future improvements

Current limitations and possible future improvements include:

- JSON-based storage instead of a database.
- Data persistence limitations on free hosting platforms.
- Migration to PostgreSQL or another database for durable storage.
- Automated backups and recovery workflows.
- Expanded accessibility and security testing.
- Locally hosted frontend assets for offline use and stricter asset integrity.

## Credits and copyright

Developed by **Pritam Rabha** as an independent MCA Python Programming academic project.

**Project Guide:** Dr. Pangambam Sendash Singh  
**Institution:** Dr. Hari Singh Gour Vishwavidyalaya, Sagar, Madhya Pradesh

Copyright © 2026 Pritam Rabha. All rights reserved.

The institution's name is included for academic identification only. This project is not an official university application and does not imply university endorsement. Third-party libraries and assets remain subject to their respective licences.
