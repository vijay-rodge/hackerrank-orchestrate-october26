"""
Unit tests for Identity Resolution.
"""

import pytest
from ghost_auditor.ingestion import DatasetContainer
from ghost_auditor.identity_resolution import IdentityResolver


def test_current_identity_resolution():
    dataset = DatasetContainer()
    resolver = IdentityResolver(dataset)

    # Test resolving current email
    resolved = resolver.resolve("amina.elmasri@gmail.com")
    assert resolved is not None
    assert resolved.user_id is not None
    assert "amina.elmasri@gmail.com" in resolved.emails


def test_historical_audit_log_resolution():
    dataset = DatasetContainer()
    resolver = IdentityResolver(dataset)

    # Test resolving historical email that changed
    sample_audit = None
    for a in dataset.audit_logs:
        if a.field_name == "email" and a.old_value:
            sample_audit = a
            break

    assert sample_audit is not None
    resolved = resolver.resolve(sample_audit.old_value)
    assert resolved is not None
    assert resolved.user_id == sample_audit.user_id
    assert sample_audit.old_value.lower() in resolved.emails

