"""End-to-end tests for Phase 2: Data Quality -> Confidence -> Review -> Lead Master.

Three test cases:
    Case 1: High-quality lead -> High confidence -> Lead Master
    Case 2: Low-confidence lead -> Review Queue
    Case 3: Duplicate lead -> Duplicate handling
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import StandardLead
from app.quality.cleaning import clean_lead
from app.quality.validation import validate_lead
from app.quality.duplicate import detect_duplicates
from app.quality.engine import run_quality_check
from app.quality.confidence import calculate_confidence
from app.review.queue import ReviewQueue
from app.lead_master.store import LeadMasterStore
from app.phase2 import Phase2Pipeline


def _print_section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def _print_subsection(title: str):
    print(f"\n  --- {title} ---")


# ============================================================================
# CASE 1: High-quality lead
# ============================================================================
def test_case_1_high_quality():
    """Valid information, good evidence, no conflicts, no duplicate -> High confidence -> Lead Master."""
    _print_section("CASE 1: High-Quality Lead -> Lead Master")

    lead = {
        "LeadId": "lead_hq001",
        "Date": "2026-08-18",
        "Category": "SaaS",
        "Segment": None,
        "Industry": "SaaS",
        "Company Name": "  Zoho Corporation  ",
        "Website": "https://www.zoho.com/",
        "Founded": "1996",
        "Revenue": "$500M",
        "City/Country": "Chennai, India",
        "Ceo/Founder Name": "sridhar vembu",
        "CEO Linkedn": "https://www.linkedin.com/in/sridhar-vembu",
        "Marketing Head name": "praval singh",
        "Marketing Head Linkedn": "https://www.linkedin.com/in/praval-singh",
        "Contact email": "sridhar.vembu@zoho.com",
        "evidence_refs": ["ev_001", "ev_002", "ev_003", "ev_004"],
        "missing_fields": [],
    }

    # Step 1: Cleaning
    _print_subsection("Step 1: Cleaning")
    cleaned = clean_lead(lead)
    print(f"  Company:  '{lead['Company Name']}' -> '{cleaned['company_name']}'")
    print(f"  Website:  '{lead['Website']}' -> '{cleaned['website']}'")
    print(f"  CEO:      '{lead['Ceo/Founder Name']}' -> '{cleaned['ceo_founder_name']}'")
    print(f"  MH:       '{lead['Marketing Head name']}' -> '{cleaned['marketing_head_name']}'")
    print(f"  Email:    '{lead['Contact email']}' -> '{cleaned['contact_email']}'")
    print(f"  LinkedIn: '{lead['CEO Linkedn']}' -> '{cleaned['ceo_linkedin']}'")

    # Step 2: Validation
    _print_subsection("Step 2: Validation")
    validation = validate_lead(cleaned)
    for v in validation:
        status_icon = "[OK]" if v.status == "valid" else "[X]" if v.status == "invalid" else "?"
        print(f"  [{status_icon}] {v.field}: {v.status} {v.issues if v.issues else ''}")

    # Step 3: Duplicate Detection
    _print_subsection("Step 3: Duplicate Detection")
    dup = detect_duplicates(cleaned, [])
    print(f"  Is duplicate: {dup.is_duplicate}")

    # Step 4: Data Quality Result
    _print_subsection("Step 4: Data Quality Result")
    dq = run_quality_check(lead, existing_leads=[])
    print(f"  Issues: {dq.issues if dq.issues else 'None'}")
    print(f"  Conflicts: {[c.field for c in dq.conflicts] if dq.conflicts else 'None'}")

    # Step 5: Confidence
    _print_subsection("Step 5: Confidence Scoring")
    conf = calculate_confidence(dq)
    print(f"  Score: {conf.score}/100")
    print(f"  Level: {conf.level}")
    print(f"  Positive: {conf.positive_factors}")
    print(f"  Negative: {conf.negative_factors}")

    # Step 6: Routing
    _print_subsection("Step 6: Routing Decision")
    if conf.level == "high":
        print(f"  -> HIGH CONFIDENCE -> Lead Master (no review needed)")
    elif conf.level == "medium":
        print(f"  -> MEDIUM CONFIDENCE -> Review Queue")
    else:
        print(f"  -> LOW/CONFLICT -> Review Queue")

    # Step 7: Lead Master
    _print_subsection("Step 7: Lead Master")
    with tempfile.TemporaryDirectory() as tmpdir:
        lm = LeadMasterStore(os.path.join(tmpdir, "lead_master.json"))
        rq = ReviewQueue(os.path.join(tmpdir, "review_queue.json"))
        pipeline = Phase2Pipeline(review_queue=rq, lead_master=lm)

        result = pipeline.process_single_lead(lead, research_job_id="job_001")
        routing = result["routing"]

        if routing["action"] == "added_to_master":
            master = lm.get_by_id(routing["master_id"])
            print(f"  Master ID: {master.master_id}")
            print(f"  Company:   {master.company_name}")
            print(f"  CEO:       {master.ceo_founder_name}")
            print(f"  Email:     {master.contact_email}")
            print(f"  Confidence: {master.confidence_score} ({master.confidence_level})")
            print(f"  Status:    {master.status}")
            print(f"  Records in Lead Master: {lm.count()}")
        else:
            print(f"  Unexpected routing: {routing}")

    print(f"\n  [OK] CASE 1 PASSED: High-quality lead -> Lead Master")
    return True


# ============================================================================
# CASE 2: Low-confidence lead
# ============================================================================
def test_case_2_low_confidence():
    """Missing/invalid information -> Low confidence -> Review Queue."""
    _print_section("CASE 2: Low-Confidence Lead -> Review Queue")

    lead = {
        "LeadId": "lead_lq001",
        "Date": "2026-08-18",
        "Category": None,
        "Segment": None,
        "Industry": None,
        "Company Name": "Some Random Corp",
        "Website": None,
        "Founded": None,
        "Revenue": None,
        "City/Country": None,
        "Ceo/Founder Name": None,
        "CEO Linkedn": None,
        "Marketing Head name": None,
        "Marketing Head Linkedn": None,
        "Contact email": None,
        "evidence_refs": ["ev_001"],
        "missing_fields": [
            "Industry", "Website", "Founded", "Revenue", "City/Country",
            "Ceo/Founder Name", "Marketing Head name", "Contact email",
        ],
    }

    # Run full pipeline
    _print_subsection("Pipeline Run")
    with tempfile.TemporaryDirectory() as tmpdir:
        lm = LeadMasterStore(os.path.join(tmpdir, "lead_master.json"))
        rq = ReviewQueue(os.path.join(tmpdir, "review_queue.json"))
        pipeline = Phase2Pipeline(review_queue=rq, lead_master=lm)

        result = pipeline.process_single_lead(lead)
        dq = result["dq_result"]
        conf = result["confidence"]
        routing = result["routing"]

        print(f"  Issues: {dq.issues}")
        print(f"  Score: {conf.score}/100")
        print(f"  Level: {conf.level}")
        print(f"  Negative: {conf.negative_factors}")
        print(f"  Routing: {routing['action']}")

        if routing["action"] == "sent_to_review":
            pending = rq.get_pending()
            print(f"  Review Queue size: {len(pending)}")
            item = pending[0]
            print(f"  Review ID: {item.review_id}")
            print(f"  Reason: {item.reason}")
            print(f"  Lead: {item.lead_data.get('Company Name')}")

    print(f"\n  [OK] CASE 2 PASSED: Low-confidence lead -> Review Queue")
    return True


# ============================================================================
# CASE 3: Duplicate lead
# ============================================================================
def test_case_3_duplicate():
    """Existing duplicate -> Duplicate handling."""
    _print_section("CASE 3: Duplicate Lead -> Duplicate Handling")

    # First lead (already in Lead Master)
    existing_lead = {
        "LeadId": "lead_dup001",
        "Date": "2026-08-18",
        "Category": "SaaS",
        "Segment": None,
        "Industry": "SaaS",
        "Company Name": "Freshworks",
        "Website": "https://freshworks.com",
        "Founded": "2010",
        "Revenue": "$200M",
        "City/Country": "Chennai, India",
        "Ceo/Founder Name": "Girish Mathrubootham",
        "CEO Linkedn": "https://www.linkedin.com/in/girish-mathrubootham",
        "Marketing Head name": "Dave Ranson",
        "Marketing Head Linkedn": None,
        "Contact email": "girish@freshworks.com",
        "evidence_refs": ["ev_001", "ev_002"],
        "missing_fields": [],
    }

    # Duplicate lead (same email)
    duplicate_lead = {
        "LeadId": "lead_dup002",
        "Date": "2026-08-18",
        "Category": "SaaS",
        "Segment": None,
        "Industry": "SaaS",
        "Company Name": "Freshworks Inc",
        "Website": "https://freshworks.com/",
        "Founded": "2010",
        "Revenue": "$200M",
        "City/Country": "Chennai, India",
        "Ceo/Founder Name": "Girish Mathrubootham",
        "CEO Linkedn": "https://www.linkedin.com/in/girish-mathrubootham",
        "Marketing Head name": "Dave Ranson",
        "Marketing Head Linkedn": None,
        "Contact email": "girish@freshworks.com",
        "evidence_refs": ["ev_003", "ev_004"],
        "missing_fields": [],
    }

    _print_subsection("Step 1: Seed Lead Master with existing lead")
    with tempfile.TemporaryDirectory() as tmpdir:
        lm = LeadMasterStore(os.path.join(tmpdir, "lead_master.json"))
        rq = ReviewQueue(os.path.join(tmpdir, "review_queue.json"))
        pipeline = Phase2Pipeline(review_queue=rq, lead_master=lm)

        # Add first lead to master
        result1 = pipeline.process_single_lead(existing_lead)
        print(f"  First lead: {result1['routing']['action']}")
        print(f"  Lead Master count: {lm.count()}")

        # Process duplicate
        _print_subsection("Step 2: Process duplicate lead")
        result2 = pipeline.process_single_lead(duplicate_lead)
        dq = result2["dq_result"]
        conf = result2["confidence"]
        routing = result2["routing"]

        print(f"  Duplicate detected: {dq.duplicate_result.is_duplicate}")
        print(f"  Match reason: {dq.duplicate_result.match_reason}")
        print(f"  Matched lead: {dq.duplicate_result.matched_lead_id}")
        print(f"  Score: {conf.score}/100 (reduced by duplicate penalty)")
        print(f"  Routing: {routing['action']}")

        if routing["action"] == "duplicate_skipped":
            print(f"  Lead Master count (unchanged): {lm.count()}")

    print(f"\n  [OK] CASE 3 PASSED: Duplicate lead -> Skipped")
    return True


# ============================================================================
# Run all tests
# ============================================================================
def main():
    print("\n" + "=" * 70)
    print("  PHASE 2 END-TO-END TESTS")
    print("  Data Quality -> Confidence -> Review -> Lead Master")
    print("=" * 70)

    results = []
    results.append(("Case 1: High-Quality Lead", test_case_1_high_quality()))
    results.append(("Case 2: Low-Confidence Lead", test_case_2_low_confidence()))
    results.append(("Case 3: Duplicate Lead", test_case_3_duplicate()))

    _print_section("TEST SUMMARY")
    for name, passed in results:
        status = "[OK] PASS" if passed else "[X] FAIL"
        print(f"  {status}  {name}")

    all_passed = all(r[1] for r in results)
    print(f"\n  {'All tests passed!' if all_passed else 'Some tests failed.'}")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
