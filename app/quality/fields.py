from __future__ import annotations

# Canonical Standard Lead JSON keys, kept in one place so a schema tweak
# is a one-line change. These MUST match app/models.py aliases exactly,
# including the "Linkedn" spelling used in the current schema.

LEAD_ID = "LeadId"
DATE = "Date"
CATEGORY = "Category"
SEGMENT = "Segment"
INDUSTRY = "Industry"
COMPANY_NAME = "Company Name"
WEBSITE = "Website"
FOUNDED = "Founded"
REVENUE = "Revenue"
CITY_COUNTRY = "City/Country"
CEO_NAME = "Ceo/Founder Name"
CEO_LINKEDIN = "CEO Linkedn"
MKT_NAME = "Marketing Head name"
MKT_LINKEDIN = "Marketing Head Linkedn"
CONTACT_EMAIL = "Contact email"

ALL_FIELDS = [
    LEAD_ID, DATE, CATEGORY, SEGMENT, INDUSTRY, COMPANY_NAME, WEBSITE,
    FOUNDED, REVENUE, CITY_COUNTRY, CEO_NAME, CEO_LINKEDIN, MKT_NAME,
    MKT_LINKEDIN, CONTACT_EMAIL,
]

# Fields that must be present for a lead to be usable at all.
REQUIRED_FIELDS = [COMPANY_NAME, WEBSITE]

# Fields that count toward the completeness component of the quality score,
# with weights (identity/contact fields matter more than metadata).
COMPLETENESS_WEIGHTS = {
    COMPANY_NAME: 3.0,
    WEBSITE: 3.0,
    CONTACT_EMAIL: 2.5,
    CEO_NAME: 1.5,
    MKT_NAME: 1.0,
    CEO_LINKEDIN: 1.0,
    MKT_LINKEDIN: 0.75,
    INDUSTRY: 1.0,
    CITY_COUNTRY: 1.0,
    FOUNDED: 0.5,
    REVENUE: 0.5,
    CATEGORY: 0.5,
    SEGMENT: 0.25,
}
