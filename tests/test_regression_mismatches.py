"""
Regression tests covering the 5 root-cause status mismatches and full public sample fidelity.
"""

import csv
import json
import pytest
from ghost_auditor.ingestion import DatasetContainer
from ghost_auditor.pipeline import DeletionAuditorPipeline


@pytest.fixture(scope="module")
def pipeline():
    ds = DatasetContainer()
    return DeletionAuditorPipeline(ds)


def test_regression_case_06_sql_search_primary(pipeline):
    """
    Case 06: Search index primary database snapshot (evidence_57).
    Root cause: search_documents_primary table was unhandled in SQL extractor.
    Fix: Added table parsing extracting search_001.
    """
    req = [r for r in pipeline.dataset.sample_requests if r.case_id == "case_06"][0]
    res = pipeline.audit_case(req)
    assert res.deletion_status == "INCOMPLETE"
    findings = [s for s in res.steps if s.phase == "FINDING"]
    assert len(findings) == 1
    assert findings[0].resource_id == "search_001"
    assert findings[0].operation == "REPORT_REMAINING_RECORD"
    assert findings[0].evidence_id == "evidence_57"


def test_regression_case_08_json_export_jobs(pipeline):
    """
    Case 08: Customer export jobs JSON snapshot (evidence_59).
    Root cause: customer_export_jobs collection was omitted from JSON extractor.
    Fix: Added handler for customer_export_jobs collection extracting export_001.
    """
    req = [r for r in pipeline.dataset.sample_requests if r.case_id == "case_08"][0]
    res = pipeline.audit_case(req)
    assert res.deletion_status == "INCOMPLETE"
    findings = [s for s in res.steps if s.phase == "FINDING"]
    assert len(findings) == 1
    assert findings[0].resource_id == "export_001"
    assert findings[0].operation == "REPORT_REMAINING_RECORD"
    assert findings[0].evidence_id == "evidence_59"


def test_regression_case_10_log_trace_correlation(pipeline):
    """
    Case 10: Multi-line support replica log (evidence_61).
    Root cause: Line-by-line parsing failed to join lookup_key on line 4 with resource_id on line 5.
    Fix: Multi-line trace correlation by trace_id (tr-rp-002) joins subject and resource.
    """
    req = [r for r in pipeline.dataset.sample_requests if r.case_id == "case_10"][0]
    res = pipeline.audit_case(req)
    assert res.deletion_status == "INCOMPLETE"
    findings = [s for s in res.steps if s.phase == "FINDING"]
    assert len(findings) == 1
    assert findings[0].resource_id == "support_002"
    assert findings[0].operation == "REPORT_REMAINING_RECORD"
    assert findings[0].evidence_id == "evidence_61"


def test_regression_case_12_historical_email_hash(pipeline):
    """
    Case 12: Historical SHA-256 email hash correlation (evidence_01).
    Root cause: analytics_9914 logged with historical hash not matched to resolved identity.
    Fix: Populated email_hash in facts and matched against resolved.email_hashes.
    """
    req = [r for r in pipeline.dataset.sample_requests if r.case_id == "case_12"][0]
    res = pipeline.audit_case(req)
    assert res.deletion_status == "INCOMPLETE"
    findings = [s for s in res.steps if s.phase == "FINDING"]
    assert len(findings) == 1
    assert findings[0].resource_id == "analytics_9914"
    assert findings[0].operation == "REPORT_REMAINING_RECORD"
    assert findings[0].evidence_id == "evidence_01"


def test_regression_case_22_replica_record_retention(pipeline):
    """
    Case 22: Read replica and primary database snapshot (evidence_05).
    Root cause: SQL extractor skipped records present in primary; misclassified data_category.
    Fix: Parsed replica & primary tables extracting search_8911 and analytics_4440 with correct policy.
    """
    req = [r for r in pipeline.dataset.sample_requests if r.case_id == "case_22"][0]
    res = pipeline.audit_case(req)
    assert res.deletion_status == "INCOMPLETE"
    findings = [s for s in res.steps if s.phase == "FINDING"]
    assert len(findings) == 2
    res_ids = {f.resource_id for f in findings}
    assert "search_8911" in res_ids
    assert "analytics_4440" in res_ids


def test_all_32_samples_100_percent_fidelity(pipeline):
    """
    Validate that all 32 public sample cases match ground truth 100% on:
    - Status
    - Steps
    - Fields
    - Sequence
    """
    sample_outs = {
        r["case_id"]: r
        for r in csv.DictReader(open(pipeline.dataset.dataset_dir / "sample_output.csv", encoding="utf-8"))
    }

    for req in pipeline.dataset.sample_requests:
        cid = req.case_id
        exp = sample_outs[cid]
        exp_status = exp["deletion_status"]
        exp_steps = json.loads(exp["steps_json"])

        pred_res = pipeline.audit_case(req)
        assert pred_res.deletion_status == exp_status, f"Status mismatch on {cid}"

        pred_steps = [s.model_dump() for s in pred_res.steps]
        assert len(pred_steps) == len(exp_steps), f"Step count mismatch on {cid}: pred={len(pred_steps)}, exp={len(exp_steps)}"

        for e_step, p_step in zip(exp_steps, pred_steps):
            assert p_step["step_no"] == e_step["step_no"], f"Step no mismatch on {cid}"
            assert p_step["phase"] == e_step["phase"], f"Phase mismatch on {cid}"
            assert p_step["system_id"] == e_step["system_id"], f"System ID mismatch on {cid}"
            assert p_step["resource_id"] == e_step["resource_id"], f"Resource ID mismatch on {cid}"
            assert p_step["operation"] == e_step["operation"], f"Operation mismatch on {cid}"
            assert p_step["state"] == e_step["state"], f"State mismatch on {cid}"
            assert p_step["evidence_id"] == e_step["evidence_id"], f"Evidence ID mismatch on {cid}"

