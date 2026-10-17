# Felix Business Manager

A client and business management application built with FastAPI, PostgreSQL,
SQLAlchemy, HTML, CSS, and JavaScript.

## Features

- Client records: create, search, view, update, and delete.
- Project tracking: status, budgets, and due dates.
- Client interactions: record calls, meetings, emails, and notes.
- Dashboard: client, project, and interaction statistics.
- Responsive blue-themed interface.
- FastAPI API documentation.

## Local setup

1. Install PostgreSQL and Python.
2. Create and activate a Python virtual environment.
3. Install dependencies:

   `python -m pip install -r requirements.txt`

4. Create a private `.env` file with your PostgreSQL connection string.
5. Start the application:

   `python -m uvicorn app.main:app --reload`

6. Open http://127.0.0.1:8000 in your browser.
7. Open http://127.0.0.1:8000/docs for interactive API documentation.

The application creates missing database tables when it starts. It does not
automatically migrate existing table structures.

## Security

The initial version is intended for local development. Authentication,
authorization, production deployment hardening, backups, and database
migrations must be implemented before exposing business records publicly.

Never commit `.env` or publish database credentials.
