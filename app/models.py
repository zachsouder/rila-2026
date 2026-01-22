from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    # From CSV
    website = Column(String)
    primary_industry = Column(String)
    num_locations = Column(Integer, default=0)  # Retail locations (leading indicator)
    employees = Column(Integer, default=0)
    revenue = Column(String)  # Keep as string for "Over $5 bil." etc.

    # Research results
    overview = Column(Text)  # 1-2 sentence description
    dc_count = Column(Integer, default=0)  # Estimated distribution centers
    truck_count = Column(Integer, default=0)  # Estimated fleet size
    company_bullets = Column(JSON)  # ["14 DCs across midwest (company website)", ...]
    hook = Column(Text)  # Recent news or key insight for conversation starter

    # Fit scores (0-100)
    gate_fit_score = Column(Integer, default=0)
    truck_fit_score = Column(Integer, default=0)
    combined_score = Column(Integer, default=0)

    # Classification
    category = Column(String, default="other")  # 'gate', 'truck', 'both', 'other'

    # Timestamps
    researched_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    attendees = relationship("Attendee", back_populates="company")


class Attendee(Base):
    __tablename__ = "attendees"

    id = Column(Integer, primary_key=True)

    # From CSV
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    company_id = Column(Integer, ForeignKey("companies.id"))
    job_title = Column(String)  # Specific: "Director, National Product Leader - Retail"
    job_function = Column(String)  # Category: "Product Management"
    management_level = Column(String)  # "Director", "VP-Level", etc.
    ticket_type = Column(String)  # "Retailer/CPG", "Exhibitor/Sponsor"
    email = Column(String)
    linkedin_url = Column(String)
    rep = Column(String)  # Assigned sales rep (for Gate team filtering)

    # Research results
    person_bullets = Column(JSON)  # ["Oversees West Coast DC network", "15+ years in logistics"]

    # Inherited from company (denormalized for fast queries)
    gate_fit_score = Column(Integer, default=0)
    truck_fit_score = Column(Integer, default=0)
    combined_score = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())

    company = relationship("Company", back_populates="attendees")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
