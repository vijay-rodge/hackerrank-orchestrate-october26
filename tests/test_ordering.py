"""
Unit tests for Step Ordering and Contract Renumbering.
"""

import pytest
from ghost_auditor.models import AuditStep
from ghost_auditor.ordering import sort_and_renumber_steps


def test_phase_ordering():
    steps = [
        AuditStep(step_no=1, phase="VERIFICATION", system_id="account_service", resource_id="account_001", operation="VERIFY_RECORD_ABSENT", state="ABSENT", evidence_id=""),
        AuditStep(step_no=2, phase="FINDING", system_id="search_service", resource_id="search_001", operation="REPORT_REMAINING_RECORD", state="PRESENT", evidence_id="evidence_57"),
        AuditStep(step_no=3, phase="REMEDIATION", system_id="search_service", resource_id="search_001", operation="DELETE_RECORD", state="ABSENT", evidence_id=""),
    ]

    sorted_steps = sort_and_renumber_steps(steps)
    assert len(sorted_steps) == 3
    assert sorted_steps[0].phase == "FINDING"
    assert sorted_steps[0].step_no == 1

    assert sorted_steps[1].phase == "REMEDIATION"
    assert sorted_steps[1].step_no == 2

    assert sorted_steps[2].phase == "VERIFICATION"
    assert sorted_steps[2].step_no == 3


def test_operation_and_resource_tie_breaking():
    steps = [
        AuditStep(step_no=99, phase="FINDING", system_id="search_service", resource_id="search_002", operation="REPORT_REMAINING_RECORD", state="PRESENT", evidence_id="ev1"),
        AuditStep(step_no=88, phase="FINDING", system_id="search_service", resource_id="search_001", operation="REPORT_REMAINING_RECORD", state="PRESENT", evidence_id="ev2"),
        AuditStep(step_no=77, phase="FINDING", system_id="analytics_platform", resource_id="analytics_001", operation="REPORT_EXPOSED_PII", state="PRESENT", evidence_id="ev3"),
    ]

    sorted_steps = sort_and_renumber_steps(steps)
    # REPORT_REMAINING_RECORD comes before REPORT_EXPOSED_PII
    assert sorted_steps[0].operation == "REPORT_REMAINING_RECORD"
    assert sorted_steps[0].resource_id == "search_001"
    assert sorted_steps[0].step_no == 1

    assert sorted_steps[1].operation == "REPORT_REMAINING_RECORD"
    assert sorted_steps[1].resource_id == "search_002"
    assert sorted_steps[1].step_no == 2

    assert sorted_steps[2].operation == "REPORT_EXPOSED_PII"
    assert sorted_steps[2].resource_id == "analytics_001"
    assert sorted_steps[2].step_no == 3

