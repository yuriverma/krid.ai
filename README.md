# Action Tracker Service

A Python-based Action Tracker service that processes RM-Client chat messages, extracts structured action items, and manages them with full audit trails.

## Features

- Message processing with deduplication
- Rule-based action extraction
- Deterministic action matching
- Complete audit trail
- REST API with Swagger documentation
- Admin interface for management

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Start the Service

```bash
uvicorn main:app --reload
```

### Run Demo

```bash
python3 demo.py
```

### Admin Interface

```bash
python3 admin.py
```

### Run Tests

```bash
python3 -m pytest tests/ -v
```

## API Endpoints

- `POST /process_chat` - Process chat messages
- `GET /actions` - Retrieve actions
- `PUT /actions/{id}/close` - Close action
- `POST /actions/{id}/merge` - Merge actions
- `GET /actions/{id}/history` - Get action history
- `GET /health` - Health check

## API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

## Project Structure

- `main.py` - FastAPI application
- `models.py` - Data models
- `db.py` - Database management
- `nlp.py` - Action extraction
- `matcher.py` - Action matching logic
- `history_logger.py` - Audit trail system
- `admin.py` - Admin interface
- `demo.py` - Demo script
- `tests/` - Test suite

## Database

SQLite database with automatic table creation. Tables:
- `actions` - Main action items
- `actions_history` - Audit trail
- `messages` - Processed messages

## Action Types

- PAN Card
- Aadhaar
- Bank Statement
- Income Proof
- Address Proof
- Photo
- Signature
- Other

## Matching Logic

- Exact match: Same task key
- Fuzzy match: Confidence-based matching
- Tentative actions: Low confidence matches for manual review