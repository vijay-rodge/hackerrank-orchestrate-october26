"""
Unit tests for output.csv schema compliance and integrity.
"""

import os
import csv
import json
import pytest
from ghost_auditor.cli import validate_output
from ghost_auditor.models import AuditStep


def test_output_csv_existence_and_contract():
    output_path = "output.csv"
    assert os.path.exists(output_path), "output.csv must exist at repository root"
    is_valid = validate_output(output_path, expected_rows=518)
    assert is_valid is True


def test_output_csv_data_rows():
    output_path = "output.csv"
    with open(output_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == 518
    # Ensure sorted by case_id ascending
    case_ids = [r["case_id"] for r in reader]
    case_nums = [int(c.split("_")[1]) for c in case_ids]
    assert case_nums == sorted(case_nums)

    for row in reader:
        assert row["deletion_status"] in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")
        steps = json.loads(row["steps_json"])
        assert isinstance(steps, list)
        if row["deletion_status"] == "NOT_APPLICABLE":
            assert steps == []
        else:
            for idx, s in enumerate(steps, 1):
                assert s["step_no"] == idx
                assert s["phase"] in ("FINDING", "REMEDIATION", "VERIFICATION")

