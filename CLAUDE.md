# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rila is a B2B sales preparation tool for conference attendees. It displays prospect information (attendees and their companies) with fit scores for two product lines: Gate Tech (distribution center security) and Truck Parking. The app uses AI-generated research to help sales reps prepare for conversations.

## Commands

### Development
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn app.main:app --reload

# Run with specific port
uvicorn app.main:app --reload --port 8000
```

### Data Pipeline
```bash
# Load CSV data and run AI research on companies
python scripts/research_companies.py

# Load CSV only (no AI research)
python scripts/research_companies.py --load-only

# Test with limited companies
python scripts/research_companies.py --limit 3
```

### Docker
```bash
docker build -t rila .
docker run -p 8000:8000 rila
```

## Architecture

### Backend (FastAPI)
- `app/main.py` - All API routes and session-based authentication
- `app/models.py` - SQLAlchemy models for Company and Attendee
- `app/database.py` - SQLite database configuration

### Frontend (Alpine.js + Jinja2)
- `app/templates/index.html` - Main SPA with Alpine.js for reactivity
- `app/templates/login.html` - Login page
- `static/style.css` - Neubrutalism design system with CSS variables

### Data Flow
1. CSV data (in `data/`) contains attendee information from conference registration
2. `scripts/research_companies.py` loads CSV → researches companies via Gemini API → saves to SQLite
3. FastAPI serves the pre-computed data with filtering/search
4. Frontend fetches via `/api/prospects` endpoint

### Key Patterns
- Company fit scores (0-100) are pre-computed during research phase
- Attendees inherit scores from their company (denormalized for fast queries)
- Categories: `gate`, `truck`, `both`, `other` based on fit score thresholds (50+)
- Session tokens stored in memory (not Redis) - simple auth for internal tool

## Environment Variables

- `SESSION_SECRET` - Secret for session tokens (auto-generated if not set)
- `GOOGLE_API_KEY` - Required for the research script (Gemini API)

## Database

SQLite database at `rila.db`. The database is committed to the repo (pre-populated with research data).
