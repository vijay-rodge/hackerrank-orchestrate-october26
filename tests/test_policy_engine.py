"""
Unit tests for Deletion Policy Engine.
"""

import pytest
from ghost_auditor.ingestion import DatasetContainer
from ghost_auditor.policy_engine import PolicyEngine


def test_policy_rule_evaluation():
    dataset = DatasetContainer()
    engine = PolicyEngine(dataset)

    # 1. User profile that is still present -> non-compliant, requires DELETE_RECORD
    is_comp, find_op, rem_op, ver_op = engine.evaluate_resource_treatment(
        system_id="account_service",
        resource_id="account_001",
        data_category="USER_PROFILE",
        is_present=True,
        is_redacted=False,
        is_anonymized=False,
        is_active=False
    )
    assert is_comp is False
    assert find_op == "REPORT_REMAINING_RECORD"
    assert rem_op == "DELETE_RECORD"
    assert ver_op == "VERIFY_RECORD_ABSENT"

    # 2. Security audit log that is present -> compliant (retained by policy)
    is_comp, find_op, rem_op, ver_op = engine.evaluate_resource_treatment(
        system_id="security_service",
        resource_id="audit_record_001",
        data_category="SECURITY_AUDIT_LOG",
        is_present=True,
        is_redacted=False,
        is_anonymized=False,
        is_active=False
    )
    assert is_comp is True
    assert ver_op == "VERIFY_RECORD_PRESENT"

    # 3. Active data flow connector -> non-compliant, requires DISABLE_DATA_FLOW
    is_comp, find_op, rem_op, ver_op = engine.evaluate_resource_treatment(
        system_id="integration_service",
        resource_id="data_flow_001",
        data_category="DATA_FLOW",
        is_present=True,
        is_redacted=False,
        is_anonymized=False,
        is_active=True
    )
    assert is_comp is False
    assert find_op == "REPORT_ACTIVE_DATA_FLOW"
    assert rem_op == "DISABLE_DATA_FLOW"
    assert ver_op == "VERIFY_DATA_FLOW_DISABLED"

