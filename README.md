# Library Management System

A web application for managing a small library: books, members, issuing and returning, automatic fines, search, and backup and restore. Written in Python with Flask and stored in a single JSON file.

## Live Demo

**Live Application:** [Student Management System](https://library-management-system-pmko.onrender.com)   


**Author:** Pritam Rabha  
**Programme:** MCA, 3rd Semester, Python Programming  
**Project Guide:** Dr. Pangambam Sendash Singh    
**Institution:** Dr. Hari Singh Gour Vishwavidyalaya, Sagar, Madhya Pradesh  


> **Academic Project Disclaimer:** This is an independent educational project prepared for an MCA Python Programming assignment. It is not an official application of Dr. Hari Singh Gour Vishwavidyalaya, Sagar, and the university has not reviewed or endorsed it. All books, members and loan records in the sample data are fictional.

---

## 1. Features

| Requirement | What the application does |
|---|---|
| Book issue and return | Issues a book to a registered member, records issue and due dates, records the return date, keeps available copies in step, and refuses to issue a book with no copies left. A member cannot hold two copies of the same title, and a configurable limit caps loans per member. |
| Fine calculation | On return, fine = overdue days x fine per day. The rate is configurable on the Settings page. Overdue days and the running fine are shown for books still on loan, and the final fine is stored with the return. |
| Book search | Search by title or author (case-insensitive, partial words, several words allowed) from the header box or the Books page, with category and availability filters. |
| User and book records | Add, view, edit and delete books and members, with input validation and duplicate protection (IDs, ISBNs, member emails). Records with books on loan cannot be deleted. |
| Available and issued books | An Available books page with copy counts, an Issued books page with borrower, issue date and due date, overdue rows highlighted and an overdue-only filter, and a full transaction history. |
| Backup and restore | Download all data as JSON with a SHA-256 checksum. Restoring is a two-step process: the file is validated and summarised, and nothing changes until the administrator ticks a confirmation box and confirms in a dialog. |

The dashboard shows total books, available copies, issued books, registered users and overdue books.

## 2. Technology

Python 3.11+, Flask, Jinja templates, Bootstrap 5.3 (loaded from the jsDelivr CDN), plain JavaScript, JSON file storage, pytest, Gunicorn.

## 3. Project structure

```
Library_Management_System/
├── app/
│   ├── __init__.py            application factory, error handlers, template filters
│   ├── config.py              environment-variable configuration, small .env loader
│   ├── security.py            login guard, CSRF protection, login throttling, security headers
│   ├── storage.py             JSON store with atomic writes and corruption handling
│   ├── routes/                thin HTTP layer (auth, main, books, members, circulation, backup)
│   ├── services/              business logic (books, members, circulation, settings,
│   │                          validators, backup, seed, clock, errors)
│   ├── templates/             Jinja templates (base layout, books/, members/, circulation/, backup/)
│   └── static/                css/style.css, js/app.js, images/dhsgu-logo.png
├── data/
│   ├── sample/sample_data.json   fictional sample books, members and loans (read-only)
│   └── runtime/                  live data file is created here (git-ignored)
├── scripts/generate_credentials.py   creates the admin password hash and a SECRET_KEY
├── tests/                     pytest suite
├── wsgi.py                    WSGI entry point (gunicorn wsgi:app)
├── render.yaml                Render deployment blueprint
├── requirements.txt           runtime dependencies
├── requirements-dev.txt       runtime plus pytest
├── pytest.ini
├── .env.example               template for local configuration
└── .gitignore
```

Sample data and runtime data are kept apart. The application only ever reads `data/sample/sample_data.json`, and uses it once, to create `data/runtime/library.json` the first time it starts (if `SEED_SAMPLE_DATA=true`). Loan dates in the sample file are relative ("issued 25 days ago"), so some loans are always overdue when you first run the project. Set `SEED_SAMPLE_DATA=false` for an empty library.

## 4. Running locally on Ubuntu

```bash
# 1. Get the code and enter the folder
unzip Library_Management_System.zip && cd Library_Management_System

# 2. Create a virtual environment (Python 3.11 or newer)
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. Create your configuration
cp .env.example .env
python scripts/generate_credentials.py --secret     # copy the output into SECRET_KEY=
python scripts/generate_credentials.py              # prompts for a password, prints ADMIN_PASSWORD_HASH=...
nano .env                                           # set ADMIN_USERNAME, SECRET_KEY, ADMIN_PASSWORD_HASH

# 4. Start the application
flask --app wsgi run --debug        # development server on http://127.0.0.1:5000
# or, as in production:
gunicorn wsgi:app --workers 1 --threads 4 --bind 127.0.0.1:8000
```

Open the address in a browser and sign in with the username you put in `.env` and the password you typed when generating the hash. The password itself is never stored anywhere; only its hash is.

Use a single Gunicorn worker. The JSON store serialises writes inside one process, so several worker processes writing the same file could overwrite each other.

### Configuration reference

| Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | `development` or `production` (production requires `SECRET_KEY`, enables secure cookies and HSTS) | `development` |
| `SECRET_KEY` | Signs session cookies. Required in production | random per start in development |
| `ADMIN_USERNAME` | Administrator username | none (login disabled until set) |
| `ADMIN_PASSWORD_HASH` | Hash from `scripts/generate_credentials.py` | none (login disabled until set) |
| `FINE_PER_DAY`, `LOAN_DAYS`, `MAX_LOANS_PER_MEMBER` | Initial values when the data file is first created. Afterwards change them on the Settings page; they are stored with the data | 2.00, 14, 5 |
| `CURRENCY_SYMBOL` | Shown beside fines | the rupee sign |
| `TIMEZONE` | Used to decide what "today" is | `Asia/Kolkata` |
| `SEED_SAMPLE_DATA` | Load sample data on first start | `true` |
| `DATA_FILE` | Location of the runtime JSON file | `data/runtime/library.json` |
| `SESSION_MINUTES` | Idle session lifetime | 30 |
| `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCK_SECONDS` | Failed-login lockout | 5 attempts, 300 seconds |

## 5. Using the application

1. **Dashboard** gives the five headline figures, the overdue loans and recent activity.
2. **Books** and **Members** list records. Use *Add*, *Edit* and *Delete*; deletions ask for confirmation.
3. **Issue a book** lets you pick an available book and a member. The due date is today plus the loan period (or a period you enter).
4. **Issued books** shows borrower and due date. Overdue rows are shaded, labelled "Overdue N days" and show the fine so far. Press *Return* to record a return; the message shows the overdue days and the fine charged.
5. **Backup and restore**: download a backup at any time. To restore, choose a file, press *Check file*, read the summary, tick the confirmation box and confirm. The previous data is saved as `library.pre-restore.json` in the data folder before it is replaced.
6. **Settings** changes the fine per day, standard loan period and loan limit.

## 6. Security notes

- The administrator password is stored only as a salted PBKDF2-SHA256 hash, supplied through an environment variable. No credentials are in the code.
- Every state-changing request needs a CSRF token (forms and the `X-CSRFToken` header). Logout is a POST request.
- Session cookies are `HttpOnly` and `SameSite=Lax`, and `Secure` in production. The session is replaced at login and expires after inactivity.
- Repeated failed logins from one address are temporarily blocked. Redirect targets after login are restricted to local paths.
- Responses carry a Content-Security-Policy, `X-Frame-Options: DENY`, `nosniff` and `no-store` cache headers. All user text is escaped by Jinja.
- Backup files are size-limited (2 MB), parsed as JSON only, checksum-verified, and fully validated (field rules, duplicate IDs, dates, referential integrity, copy counts) before they can be staged. The checksum detects accidental damage and edits; it is not a signature, so only restore files you trust.
- Bootstrap is loaded from a CDN without a Subresource Integrity attribute. For a stricter deployment, download Bootstrap into `app/static/` and change the `<link>` in `base.html`.

## 7. Testing

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

The suite covers each mandatory feature, including invalid inputs, duplicate IDs and ISBNs, unavailable books, overdue fines, and backup and restore:

| File | Covers |
|---|---|
| `test_circulation.py` | issue, return, dates, available copies, unavailable books, loan limits |
| `test_fines.py` | fine formula, configurable rate, overdue days, settings validation |
| `test_search.py` | title and author search, case, partial words, empty results, filters |
| `test_books_members.py` | add, view, edit, delete, validation, duplicates, delete protection |
| `test_listings.py` | available and issued lists, overdue highlighting, dashboard figures |
| `test_backup.py` | export, round trip, confirmation, corrupted, tampered and inconsistent files |
| `test_security.py` | login, logout, CSRF, throttling, headers, cookies, escaping |
| `test_storage.py` | atomic writes, failed writes, corrupted data file, sample data separation |

## 8. Uploading to GitHub

```bash
cd Library_Management_System
git init
git add .
git status          # check that .env and data/runtime/library.json are NOT listed
git commit -m "Library Management System: MCA Python Programming project"
git branch -M main
# create an empty repository on github.com first (no README, no .gitignore), then:
git remote add origin https://github.com/<your-username>/library-management-system.git
git push -u origin main
```

`.gitignore` already excludes `.env`, the virtual environment and the runtime data file. If you ever commit a secret by mistake, change it immediately; removing it from a later commit does not remove it from history.

## 9. Deploying on Render (Free)

1. Push the project to GitHub (section 8).
2. On [render.com](https://render.com) choose **New > Blueprint**, connect the repository and select it. Render reads `render.yaml`. (Alternatively, create a **Web Service** manually with build command `pip install -r requirements.txt` and start command `gunicorn wsgi:app --workers 1 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT`.)
3. When prompted, enter the two values marked "sync: false":
   - `ADMIN_USERNAME`: the administrator username you want.
   - `ADMIN_PASSWORD_HASH`: run `python scripts/generate_credentials.py` on your computer and paste the whole hash.
   `SECRET_KEY` is generated by Render automatically.
4. Deploy. When the build finishes, open the `onrender.com` address and sign in. `/healthz` is the health-check path.

Environment variables can be changed later under **Environment** in the Render dashboard.

### Important: Render Free does not keep your data

Render Free web services have an **ephemeral filesystem**. Files written while the service runs, including `data/runtime/library.json`, are lost whenever the service restarts, redeploys, or spins up again after idling (free services sleep after a period without traffic). After that the application starts again from the sample data (or an empty library). This is acceptable for a demonstration but not for real records. To protect your work:

- download a backup from **Backup and restore** before ending a session, and restore it after a restart;
- or run the project locally for anything you want to keep;
- or move to a paid plan with a persistent disk and set `DATA_FILE` to a path on that disk.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| "Administrator credentials are not configured" | Set `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` in `.env` (or Render environment) and restart. |
| App exits with "SECRET_KEY must be set" | Production mode needs `SECRET_KEY`; generate one with `--secret`. |
| "The data file is corrupted" page | The runtime JSON was damaged. Replace it with `library.json.bak` (the previous version), restore a backup, or delete the runtime file to start fresh. The application never overwrites a file it cannot read. |
| Page has no styling offline | Bootstrap comes from a CDN; you need internet access, or vendor the file as described in section 6. |
| Dates look off by a day | Set `TIMEZONE` to your local zone, for example `Asia/Kolkata`. |

## 11. Logo and branding

The university logo is stored at `app/static/images/dhsgu-logo.png` and is referenced everywhere with `url_for('static', filename='images/dhsgu-logo.png')`, so the path works unchanged locally and on Render. It is used on the sign-in page, beside the application name in the sidebar, and as the browser favicon. It is displayed at its natural proportions (width and height attributes plus `height: auto`) and is never cropped or recoloured. To change it, replace that file with another image of your own.

## 12. Licence and use

Provided for educational purposes. Fictional sample data only; do not store real personal information on a free demonstration deployment.
