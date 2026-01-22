#!/usr/bin/env python3
"""
Batch research script for RILA LINK 2026 attendees using Gemini 3 Flash with Google Search grounding.
Saves progress to SQLite as it goes (resumable).

Usage:
    python scripts/research_companies.py              # Run all
    python scripts/research_companies.py --limit 3    # Test with 3 companies
    python scripts/research_companies.py --load-only  # Just load CSV, no research
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.database import SessionLocal, init_db
from app.models import Company, Attendee

load_dotenv()

# Initialize Gemini client
client = genai.Client()

# Rate limiting
DELAY_BETWEEN_CALLS = 1.5  # seconds

# CSV file path
CSV_FILENAME = "2026-01 RILA LINK 2026 Attendee List (Clay and ZoomInfo Enriched) - RILA LINK 2026 Attendees.csv"

# Research prompt - focused on bullet points with sources
COMPANY_RESEARCH_PROMPT = """Research "{company_name}" for a B2B sales conversation about distribution center security and truck parking.

Context from their data:
- Industry: {industry}
- Reported locations: {num_locations}
- Employees: {employees}
- Website: {website}

I need SPECIFIC, SOURCED information. Return JSON:

{{
    "overview": "1-2 sentence description of what this company does",
    "dc_count": <number of distribution centers, fulfillment centers, or warehouses. Be specific. 0 if unknown>,
    "dc_source": "Where you found DC info: 'company website', 'press release', 'LinkedIn', 'estimated from X', etc.",
    "truck_count": <number of trucks/tractors in their fleet. 0 if they don't operate their own fleet>,
    "truck_source": "Where you found fleet info, or 'N/A - not a fleet operator'",
    "gate_fit_score": <0-100 score for gate automation fit>,
    "truck_fit_score": <0-100 score for truck parking fit>,
    "hook": "One recent news item, expansion, or key insight to use as a conversation starter. Be specific with dates. Example: 'Announced $500M DC expansion in Texas (Jan 2026)'",
    "company_bullets": [
        "Key fact about their logistics operations (source)",
        "Recent expansion or news item (source, date)",
        "Another relevant detail for sales conversation (source)"
    ]
}}

SCORING - BE STRICT:
- gate_fit_score: 90+ = 50+ DCs confirmed, 70-89 = 20-49 DCs, 50-69 = 5-19 DCs, <50 = few/unknown
- truck_fit_score: 90+ = 1000+ trucks confirmed, 70-89 = 500-999, 50-69 = 100-499, <50 = small/no fleet

For BULLETS - include source in parentheses:
- "Operates 47 DCs across North America (company careers page)"
- "Recently opened 1.2M sq ft fulfillment center in Dallas (PR Newswire, Oct 2025)"
- "Fleet of ~800 trucks for dedicated delivery (LinkedIn job posts)"

Return ONLY valid JSON, no markdown formatting."""


def parse_json_response(text: str) -> dict:
    """Extract JSON from response text, handling markdown code blocks."""
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)

    return json.loads(text)


def safe_int(value, default=0):
    """Safely convert to int, handling NaN, None, empty strings."""
    if value is None or value == '' or (isinstance(value, float) and value != value):
        return default
    try:
        # Handle strings like "10,000" or "10000"
        if isinstance(value, str):
            value = value.replace(',', '').strip()
            if not value:
                return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def research_company(company_name: str, industry: str, num_locations: int, employees: int, website: str) -> dict:
    """Research a single company using Gemini with Google Search grounding."""
    grounding_tool = types.Tool(google_search=types.GoogleSearch())

    config = types.GenerateContentConfig(
        tools=[grounding_tool],
        thinking_config=types.ThinkingConfig(thinking_level="low")
    )

    prompt = COMPANY_RESEARCH_PROMPT.format(
        company_name=company_name,
        industry=industry or "Unknown",
        num_locations=num_locations or "Unknown",
        employees=employees or "Unknown",
        website=website or "Unknown"
    )

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=config,
    )

    return parse_json_response(response.text)


def calculate_combined_score(gate_score: int, truck_score: int) -> int:
    """Calculate combined score with bonus for dual fit."""
    base = max(gate_score, truck_score)
    both_bonus = min(gate_score, truck_score) * 0.2
    return int(base + both_bonus)


def assign_category(gate_score: int, truck_score: int) -> str:
    """Assign category based on fit scores."""
    if gate_score >= 50 and truck_score >= 50:
        return "both"
    elif gate_score >= 50:
        return "gate"
    elif truck_score >= 50:
        return "truck"
    else:
        return "other"


def load_csv_data(csv_path: str) -> list:
    """Load and parse CSV data."""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def main():
    parser = argparse.ArgumentParser(description="Research RILA LINK 2026 attendee companies")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of companies to research (0 = all)")
    parser.add_argument("--load-only", action="store_true", help="Only load CSV data, skip research")
    args = parser.parse_args()

    # Initialize database
    init_db()
    db = SessionLocal()

    # Load CSV
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", CSV_FILENAME)
    attendees_data = load_csv_data(csv_path)
    print(f"Loaded {len(attendees_data)} attendees from CSV")

    # Build company info from CSV (aggregate from all attendees at each company)
    companies_from_csv = {}
    for row in attendees_data:
        company_name = row.get('Company', '').strip()
        if not company_name:
            continue

        if company_name not in companies_from_csv:
            companies_from_csv[company_name] = {
                'name': company_name,
                'website': row.get('Website', '') or row.get('Domain', ''),
                'primary_industry': row.get('Primary Industry', ''),
                'num_locations': safe_int(row.get('Number of Locations', 0)),
                'employees': safe_int(row.get('Employees', 0)),
                'revenue': row.get('Revenue Range (in USD)', '') or row.get('Revenue (in 000s USD)', ''),
            }

    print(f"Found {len(companies_from_csv)} unique companies")

    # Get existing companies from database
    existing_companies = {c.name: c for c in db.query(Company).all()}
    print(f"Already in database: {len(existing_companies)}")

    # Create or update companies from CSV data
    for company_name, csv_data in companies_from_csv.items():
        if company_name not in existing_companies:
            company = Company(
                name=company_name,
                website=csv_data['website'],
                primary_industry=csv_data['primary_industry'],
                num_locations=csv_data['num_locations'],
                employees=csv_data['employees'],
                revenue=str(csv_data['revenue']) if csv_data['revenue'] else None,
            )
            db.add(company)
            existing_companies[company_name] = company

    db.commit()
    print(f"Companies in database: {len(existing_companies)}")

    # Load attendees from CSV
    print(f"\nLoading attendees...")
    existing_attendees = {}
    for a in db.query(Attendee).join(Company).all():
        key = (a.first_name, a.last_name, a.company.name)
        existing_attendees[key] = a

    attendees_added = 0
    for row in attendees_data:
        company_name = row.get('Company', '').strip()
        first_name = row.get('First Name', '').strip()
        last_name = row.get('Last Name', '').strip()

        # If First Name is empty, try to parse from Full Name
        if not first_name:
            full_name = row.get('Full Name', '').strip()
            if full_name:
                parts = full_name.split(None, 1)  # Split on first whitespace
                first_name = parts[0] if parts else ''
                if len(parts) > 1 and not last_name:
                    last_name = parts[1]

        if not company_name or not first_name:
            continue

        key = (first_name, last_name, company_name)
        if key in existing_attendees:
            continue

        company = existing_companies.get(company_name)
        if not company:
            continue

        attendee = Attendee(
            first_name=first_name,
            last_name=last_name,
            company_id=company.id,
            job_title=row.get('Job Title', '') or row.get('Title', ''),
            job_function=row.get('Job Function', ''),
            management_level=row.get('Management Level', ''),
            ticket_type=row.get('Ticket Type', ''),
            email=row.get('Work Email', '') or row.get('Email Address', ''),
            linkedin_url=row.get('LinkedIn Contact Profile URL', '') or row.get('Linked In Profile URL', ''),
            rep=row.get('Rep', ''),
            gate_fit_score=company.gate_fit_score,
            truck_fit_score=company.truck_fit_score,
            combined_score=company.combined_score,
        )
        db.add(attendee)
        existing_attendees[key] = attendee
        attendees_added += 1

    db.commit()
    print(f"Added {attendees_added} new attendees")

    if args.load_only:
        print("\n--load-only specified, skipping research")
        db.close()
        return

    # Research companies that haven't been researched yet
    companies_to_research = [
        c for c in db.query(Company).filter(Company.researched_at == None).all()
    ]

    print(f"\nCompanies to research: {len(companies_to_research)}")

    if args.limit > 0:
        companies_to_research = companies_to_research[:args.limit]
        print(f"Limited to: {len(companies_to_research)} companies")

    for i, company in enumerate(companies_to_research):
        print(f"\n[{i+1}/{len(companies_to_research)}] Researching: {company.name}")

        try:
            research = research_company(
                company.name,
                company.primary_industry,
                company.num_locations,
                company.employees,
                company.website
            )

            gate_score = research.get('gate_fit_score', 0)
            truck_score = research.get('truck_fit_score', 0)

            company.overview = research.get('overview', '')
            company.dc_count = research.get('dc_count', 0)
            company.truck_count = research.get('truck_count', 0)
            company.company_bullets = research.get('company_bullets', [])
            company.hook = research.get('hook', '')
            company.gate_fit_score = gate_score
            company.truck_fit_score = truck_score
            company.combined_score = calculate_combined_score(gate_score, truck_score)
            company.category = assign_category(gate_score, truck_score)
            company.researched_at = datetime.now(timezone.utc)

            # Update all attendees at this company with scores
            for attendee in company.attendees:
                attendee.gate_fit_score = gate_score
                attendee.truck_fit_score = truck_score
                attendee.combined_score = company.combined_score

            db.commit()

            print(f"  ✓ DCs: {company.dc_count}, Trucks: {company.truck_count}")
            print(f"  ✓ Gate: {gate_score}, Truck: {truck_score}, Category: {company.category}")
            if company.company_bullets:
                print(f"  ✓ {len(company.company_bullets)} bullets")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            db.rollback()

        time.sleep(DELAY_BETWEEN_CALLS)

    # Summary
    total_companies = db.query(Company).count()
    researched_companies = db.query(Company).filter(Company.researched_at != None).count()
    total_attendees = db.query(Attendee).count()

    print(f"\n\n=== COMPLETE ===")
    print(f"Companies: {researched_companies}/{total_companies} researched")
    print(f"Attendees: {total_attendees}")

    # Category breakdown
    print(f"\nCategory breakdown:")
    for cat in ['gate', 'truck', 'both', 'other']:
        count = db.query(Company).filter(Company.category == cat).count()
        print(f"  {cat}: {count}")

    # Score distribution
    print(f"\nGate fit score distribution:")
    for threshold in [90, 70, 50, 0]:
        if threshold > 0:
            count = db.query(Company).filter(Company.gate_fit_score >= threshold).count()
            print(f"  {threshold}+: {count}")

    db.close()


if __name__ == "__main__":
    main()
