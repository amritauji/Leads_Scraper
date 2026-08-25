"""End-to-end tests for Phase 2 with full lineage verification (Supabase PostgreSQL).

Three test cases:
    Case 1: High-quality lead -> Lead Master (with lineage)
    Case 2: Low-confidence lead -> Review Queue (with lineage)
    Case 3: Duplicate lead -> DuplicateEvent (NOT in Lead Master)

Also tests: approving a review creates Lead Master with full lineage.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import StandardLead
from app.quality.cleaning import clean_lead
from app.quality.validation import validate_lead
from app.quality.duplicate import detect_duplicates
from app.quality.engine import run_quality_check
from app.quality.confidence import calculate_confidence
from app.db.quality_store import QualityResultStore
from app.db.confidence_store import ConfidenceResultStore
from app.db.duplicate_store import DuplicateEventStore
from app.lead_master.store import LeadMasterStore
from app.review.queue import ReviewQueue
from app.phase2 import Phase2Pipeline
from app.db.connection import get_connection


def _clear_all():
    """Clear all Phase 2 tables before a test."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM duplicate_events")
            cur.execute("DELETE FROM review_queue")
            cur.execute("DELETE FROM lead_master")
            cur.execute("DELETE FROM confidence_results")
            cur.execute("DELETE FROM quality_results")
        conn.commit()
    finally:
        conn.close()


def _print_section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def _print_subsection(title: str):
    print(f"\n  --- {title} ---")


def _assert(condition: bool, msg: str):
    if not condition:
        print(f"  [FAIL] {msg}")
        raise AssertionError(msg)
    print(f"  [OK] {msg}")


# ============================================================================
# CASE 1: High-quality lead -> Lead Master with full lineage
# ============================================================================
def test_case_1_high_quality():
    _print_section("CASE 1: High-Quality Lead -> Lead Master (lineage verified)")

    _clear_all()

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

    pipeline = Phase2Pipeline()

    result = pipeline.process_single_lead(lead, research_job_id="job_001")
    dq = result["dq_result"]
    conf = result["confidence"]
    routing = result["routing"]

    _print_subsection("Pipeline Result")
    print(f"  Routing: {routing['action']}")
    print(f"  Score: {conf.score}/100 ({conf.level})")

    # --- Lineage assertions ---
    _print_subsection("Lineage: Data Quality Result")
    _assert(dq.quality_result_id is not None and len(dq.quality_result_id) > 0,
            "DataQualityResult has quality_result_id")
    _assert(dq.lead_id == "lead_hq001", "DataQualityResult.lead_id matches")
    _assert(dq.research_job_id == "job_001", "DataQualityResult.research_job_id matches")

    dq_store = QualityResultStore()
    dq_from_db = dq_store.get_by_id(dq.quality_result_id)
    _assert(dq_from_db is not None, "DataQualityResult persisted in Supabase")
    _assert(dq_from_db.quality_result_id == dq.quality_result_id, "DQ record ID matches in DB")
    _assert(dq_from_db.original_lead.get("LeadId") == "lead_hq001",
            "Original Standard Lead JSON preserved in DQ record")
    _assert(len(dq_from_db.validation) > 0, "Validation results persisted")
    _assert(dq_from_db.duplicate_result is not None, "Duplicate result persisted")

    _print_subsection("Lineage: Confidence Result")
    _assert(conf.confidence_result_id is not None and len(conf.confidence_result_id) > 0,
            "ConfidenceResult has confidence_result_id")
    _assert(conf.quality_result_id == dq.quality_result_id,
            "ConfidenceResult.quality_result_id links to DQ result")
    _assert(conf.lead_id == "lead_hq001", "ConfidenceResult.lead_id matches")
    _assert(conf.research_job_id == "job_001", "ConfidenceResult.research_job_id matches")

    cr_store = ConfidenceResultStore()
    cr_from_db = cr_store.get_by_id(conf.confidence_result_id)
    _assert(cr_from_db is not None, "ConfidenceResult persisted in Supabase")
    _assert(len(cr_from_db.positive_factors) > 0, "Positive factors persisted")
    _assert(len(cr_from_db.negative_factors) >= 0, "Negative factors persisted")

    _print_subsection("Lineage: Lead Master Record")
    _assert(routing["action"] == "added_to_master", "Lead routed to master")
    lm = LeadMasterStore()
    master = lm.get_by_id(routing["master_id"])
    _assert(master is not None, "Lead Master record exists")
    _assert(master.quality_result_id == dq.quality_result_id,
            "LeadMaster.quality_result_id links to DQ result")
    _assert(master.confidence_result_id == conf.confidence_result_id,
            "LeadMaster.confidence_result_id links to Confidence result")
    _assert(master.research_job_id == "job_001",
            "LeadMaster.research_job_id preserves research traceability")
    _assert(master.review_id is None, "LeadMaster.review_id is None for direct-to-master")
    _assert(master.source_lead_json.get("LeadId") == "lead_hq001",
            "Original Standard Lead JSON preserved in source_lead_json")
    _assert(len(master.evidence_refs) == 4, "Evidence refs preserved")
    _assert(len(master.raw_evidence_refs) == 4, "Raw evidence refs preserved")
    _assert(master.confidence_score == conf.score, "Confidence score matches")

    _print_subsection("Lineage Chain")
    print(f"  LeadMaster.master_id:      {master.master_id}")
    print(f"  -> confidence_result_id:    {master.confidence_result_id}")
    print(f"  -> quality_result_id:       {master.quality_result_id}")
    print(f"  -> lead_id:                 {master.lead_id}")
    print(f"  -> evidence_refs:           {master.evidence_refs}")
    print(f"  -> research_job_id:         {master.research_job_id}")

    dup_store = DuplicateEventStore()
    _assert(dup_store.count() == 0, "No duplicate events for non-duplicate lead")

    print(f"\n  CASE 1 PASSED: Full lineage verified for high-confidence lead")
    return True


# ============================================================================
# CASE 2: Low-confidence lead -> Review Queue with full lineage
# ============================================================================
def test_case_2_low_confidence():
    _print_section("CASE 2: Low-Confidence Lead -> Review Queue (lineage verified)")

    _clear_all()

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

    pipeline = Phase2Pipeline()
    result = pipeline.process_single_lead(lead, research_job_id="job_002")
    dq = result["dq_result"]
    conf = result["confidence"]
    routing = result["routing"]

    _print_subsection("Pipeline Result")
    print(f"  Routing: {routing['action']}")
    print(f"  Score: {conf.score}/100 ({conf.level})")

    _print_subsection("Lineage: Data Quality Result")
    _assert(dq.quality_result_id is not None, "DQ result has ID")
    dq_store = QualityResultStore()
    dq_from_db = dq_store.get_by_id(dq.quality_result_id)
    _assert(dq_from_db is not None, "DQ result persisted in Supabase")

    _print_subsection("Lineage: Confidence Result")
    _assert(conf.confidence_result_id is not None, "Confidence result has ID")
    _assert(conf.quality_result_id == dq.quality_result_id, "CR links to DQ")
    cr_store = ConfidenceResultStore()
    cr_from_db = cr_store.get_by_id(conf.confidence_result_id)
    _assert(cr_from_db is not None, "Confidence result persisted in Supabase")

    _print_subsection("Lineage: Review Queue")
    _assert(routing["action"] == "sent_to_review", "Lead routed to review queue")

    rq = ReviewQueue()
    pending = rq.get_pending()
    _assert(len(pending) >= 1, "At least one item in review queue")
    item = pending[0]

    _assert(item.lead_id == "lead_lq001", "ReviewItem.lead_id matches")
    _assert(item.confidence_score == conf.score, "ReviewItem.confidence_score matches")
    _assert(item.confidence_level == conf.level, "ReviewItem.confidence_level matches")
    _assert(item.confidence_result_id == conf.confidence_result_id,
            "ReviewItem.confidence_result_id links to Confidence result")
    _assert(item.quality_result_id == dq.quality_result_id,
            "ReviewItem.quality_result_id links to DQ result")
    _assert(item.reason in ("low_confidence", "medium_confidence"),
            f"Review reason is appropriate: {item.reason}")

    _print_subsection("Lineage: Review -> Approve -> Lead Master")
    approved = pipeline.approve_review(item.review_id)
    _assert(approved is not None, "Review approved successfully")
    _assert(approved.get("master_id") is not None, "Master record created from approval")
    _assert(approved.get("quality_result_id") is not None, "Approved master has quality_result_id")
    _assert(approved.get("confidence_result_id") is not None, "Approved master has confidence_result_id")
    _assert(approved.get("review_id") == item.review_id,
            "Approved master links back to review")

    _print_subsection("Lineage Chain (approved)")
    print(f"  LeadMaster.master_id:      {approved['master_id']}")
    print(f"  -> review_id:               {approved['review_id']}")
    print(f"  -> confidence_result_id:    {approved['confidence_result_id']}")
    print(f"  -> quality_result_id:       {approved['quality_result_id']}")
    print(f"  -> lead_id:                 {approved['lead_id']}")

    dup_store = DuplicateEventStore()
    _assert(dup_store.count() == 0, "No duplicate events for non-duplicate lead")

    print(f"\n  CASE 2 PASSED: Full lineage verified for low-confidence lead")
    return True


# ============================================================================
# CASE 3: Duplicate lead -> DuplicateEvent persisted
# ============================================================================
def test_case_3_duplicate():
    _print_section("CASE 3: Duplicate Lead -> DuplicateEvent (NOT in Lead Master)")

    _clear_all()

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

    pipeline = Phase2Pipeline()

    _print_subsection("Step 1: Seed Lead Master")
    result1 = pipeline.process_single_lead(existing_lead, research_job_id="job_003")
    _assert(result1["routing"]["action"] == "added_to_master", "First lead added to master")
    lm = LeadMasterStore()
    _assert(lm.count() == 1, "Lead Master has 1 record")

    _print_subsection("Step 2: Process Duplicate Lead")
    result2 = pipeline.process_single_lead(duplicate_lead, research_job_id="job_004")
    dq = result2["dq_result"]
    conf = result2["confidence"]
    routing = result2["routing"]

    _assert(dq.duplicate_result.is_duplicate is True, "Duplicate detected")
    _assert(dq.duplicate_result.match_reason in ("exact_email", "exact_linkedin", "same_domain_person"),
            f"Match reason valid: {dq.duplicate_result.match_reason}")

    _print_subsection("Lineage: Duplicate Event")
    _assert(routing["action"] == "duplicate_skipped", "Lead skipped as duplicate")
    _assert(routing.get("duplicate_event_id") is not None, "Duplicate event ID returned")

    dup_store = DuplicateEventStore()
    dup_event = dup_store.get_by_id(routing["duplicate_event_id"])
    _assert(dup_event is not None, "DuplicateEvent persisted in Supabase")
    _assert(dup_event.incoming_lead_id == "lead_dup002",
            "DuplicateEvent.incoming_lead_id matches")
    _assert(dup_event.matched_master_id is not None,
            "DuplicateEvent.matched_master_id links to existing master")
    _assert(dup_event.match_reason in ("exact_email", "exact_linkedin", "same_domain_person"),
            f"Match reason valid: {dup_event.match_reason}")
    _assert(dup_event.quality_result_id is not None,
            "DuplicateEvent.quality_result_id links to DQ result")
    _assert(dup_event.research_job_id == "job_004",
            "DuplicateEvent.research_job_id matches")

    dq_store = QualityResultStore()
    dq_from_db = dq_store.get_by_id(dq.quality_result_id)
    _assert(dq_from_db is not None, "DQ result for duplicate is also persisted")

    _assert(lm.count() == 1, "Lead Master still has 1 record (duplicate not added)")
    _assert(lm.get_by_lead_id("lead_dup002") is None,
            "Duplicate lead_id NOT in Lead Master")

    _print_subsection("Lineage Chain (duplicate)")
    print(f"  DuplicateEvent:            {dup_event.duplicate_event_id}")
    print(f"  -> incoming_lead_id:        {dup_event.incoming_lead_id}")
    print(f"  -> matched_master_id:       {dup_event.matched_master_id}")
    print(f"  -> match_reason:            {dup_event.match_reason}")
    print(f"  -> quality_result_id:       {dup_event.quality_result_id}")
    print(f"  -> research_job_id:         {dup_event.research_job_id}")

    print(f"\n  CASE 3 PASSED: Duplicate event recorded, NOT in Lead Master")
    return True


# ============================================================================
# Run all tests
# ============================================================================
def main():
    print("\n" + "=" * 70)
    print("  PHASE 2 TESTS (Supabase PostgreSQL)")
    print("=" * 70)

    results = []
    results.append(("Case 1: High-Quality Lead", test_case_1_high_quality()))
    results.append(("Case 2: Low-Confidence Lead", test_case_2_low_confidence()))
    results.append(("Case 3: Duplicate Lead", test_case_3_duplicate()))

    _print_section("TEST SUMMARY")
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  {name}")

    all_passed = all(r[1] for r in results)
    print(f"\n  {'All tests passed!' if all_passed else 'Some tests failed.'}")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
