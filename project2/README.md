# TransferDB

TransferDB is a Flask and MySQL web application for managing football transfer, match, squad, and competition data across multiple user roles.

This project was developed for **CMPE 321 - Database Management Systems** as a **two-person team project**. The main scope was to implement a database-backed application with normalized relational design, SQL constraints, triggers, stored procedures, secure password handling, and role-based workflows.

## Features

- Role-based login for database managers, players, managers, and referees
- Secure password hashing with bcrypt
- Database manager workflows for stadiums, match scheduling, transfers, manager assignments, and competition creation
- Player dashboards for profile details, statistics, match history, and career history
- Manager workflows for fixtures, standings, squad statistics, competition leaderboards, and squad submission
- Referee workflows for match history, career statistics, and result submission
- MySQL schema with constraints, triggers, and a stored procedure for enforcing business rules
- Initial dataset loader from Excel for demo data

## Tech Stack

- Python
- Flask
- MySQL
- mysql-connector-python
- bcrypt
- openpyxl
- Bootstrap 5 templates

## User Flow

1. Set up the MySQL schema and triggers.
2. Load the initial Excel dataset.
3. Start the Flask app.
4. Log in as one of the seeded users.
5. Use the sidebar to access role-specific operations.

Seeded demo accounts are loaded from `initial_data.xlsx`:

| Role | Username | Password |
| --- | --- | --- |
| Database Manager | `kevin` | `K3v!n#2024` |
| Player | `arda_guler` | `hash_Str0ng!2` |
| Referee | `cuneyt_cakir` | `hash_R3feree!` |
| Manager | `fatih_terim` | `hash_M@nager1` |

## Running Locally

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure MySQL

Create local environment variables for your MySQL connection. You can use `.env.example` as a reference, but this project reads variables from the shell environment.

```bash
export TRANSFERDB_DB_HOST=127.0.0.1
export TRANSFERDB_DB_USER=root
export TRANSFERDB_DB_PASSWORD='your_mysql_password'
export TRANSFERDB_DB_NAME=TransferDB
export TRANSFERDB_SECRET_KEY='local-dev-secret'
```

The SQL files create and use the `TransferDB` database by default.

### 3. Create the database schema

```bash
python setup_db.py
```

This runs:

- `sql/schema.sql`
- `sql/triggers.sql`

### 4. Load demo data

```bash
python load_initial_data.py
```

### 5. Start the app

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

## Project Structure

```text
.
├── app.py                  # Flask routes and role-based workflows
├── config.py               # Environment-based app and database config
├── db.py                   # MySQL connection and query helpers
├── setup_db.py             # Schema and trigger setup script
├── load_initial_data.py    # Excel-to-MySQL seed data loader
├── db_check.py             # Local database inspection helper
├── initial_data.xlsx       # Demo dataset
├── requirements.txt        # Python dependencies
├── sql/
│   ├── schema.sql          # Database schema
│   └── triggers.sql        # Triggers and stored procedure
└── templates/              # Bootstrap/Jinja templates by role
```

Course submission PDFs and personal report artifacts are kept locally in `_archive/`, which is ignored by git.

## Skills Demonstrated

- Relational schema design and normalization
- SQL constraints, triggers, and stored procedure implementation
- Flask route design and role-based access control
- Secure password hashing and validation
- Parameterized SQL query usage
- Excel data ingestion with Python
- Multi-role CRUD workflow implementation



