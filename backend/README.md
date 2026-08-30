# Obligation Agent — Backend Engine

FastAPI backend with asynchronous SQLAlchemy ORM, Pydantic V2 validation, Alembic migrations, and an extensible extraction provider architecture.

## Getting Started

1. Create & activate Python virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1 # On Windows
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Seed canonical demo data:
   ```bash
   python seed.py
   ```
4. Run tests:
   ```bash
   python -m pytest -v
   ```
5. Start dev server:
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```
