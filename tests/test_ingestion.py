"""
Unit tests for Dataset Ingestion.
"""

import os
import pytest
from ghost_auditor.ingestion import DatasetContainer


def test_dataset_ingestion():
    dataset = DatasetContainer()
    assert len(dataset.requests) == 518
    assert len(dataset.sample_requests) == 32
    assert len(dataset.identities) >= 800
    assert len(dataset.audit_logs) >= 300
    assert len(dataset.activities) >= 4000
    assert len(dataset.rules) == 15
    assert len(dataset.evidence_manifest) == 94


def test_unique_case_ids():
    dataset = DatasetContainer()
    case_ids = [r.case_id for r in dataset.requests]
    assert len(case_ids) == len(set(case_ids))
    assert case_ids[0] == "case_33"
    assert case_ids[-1] == "case_550"

