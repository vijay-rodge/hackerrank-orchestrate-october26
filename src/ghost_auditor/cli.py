"""
Command-Line Interface for Ghost Data Auditor.
"""

import sys
import os
import argparse
import logging
from typing import List

from ghost_auditor.ingestion import DatasetContainer
from ghost_auditor.pipeline import DeletionAuditorPipeline
from ghost_auditor.models import CaseAuditResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ghost_auditor.cli")


def run_audit(dataset_dir: str = "dataset", output_path: str = "output.csv", use_samples: bool = False):
    """Run audit and output predictions."""
    logger.info(f"Loading datasets from {dataset_dir}...")
    dataset = DatasetContainer(dataset_dir)
    pipeline = DeletionAuditorPipeline(dataset)

    requests = dataset.sample_requests if use_samples else dataset.requests
    logger.info(f"Running audit on {len(requests)} cases (use_samples={use_samples})...")
    results = pipeline.run_all(requests)

    logger.info(f"Writing output to {output_path}...")
    pipeline.write_output_csv(results, output_path)
    logger.info("Audit run completed successfully.")


def validate_output(output_path: str = "output.csv", expected_rows: int = 518) -> bool:
    """Validate output CSV structure and JSON schemas."""
    import csv
    import json
    from ghost_auditor.models import AuditStep

    if not os.path.exists(output_path):
        logger.error(f"Output file does not exist: {output_path}")
        return False

    with open(output_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["case_id", "deletion_status", "steps_json"]:
            logger.error(f"Invalid columns: {reader.fieldnames}. Expected: ['case_id', 'deletion_status', 'steps_json']")
            return False

        rows = list(reader)
        if len(rows) != expected_rows:
            logger.error(f"Expected {expected_rows} data rows, found {len(rows)}")
            return False

        prev_id_num = -1
        for idx, row in enumerate(rows, 1):
            cid = row["case_id"]
            status = row["deletion_status"]
            steps_raw = row["steps_json"]

            # Validate ID order
            try:
                curr_num = int(cid.split("_")[1])
                if curr_num <= prev_id_num:
                    logger.error(f"Row {idx} out of order: {cid} after {prev_id_num}")
                    return False
                prev_id_num = curr_num
            except Exception:
                pass

            if status not in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"):
                logger.error(f"Row {idx} ({cid}) has invalid status: {status}")
                return False

            try:
                steps = json.loads(steps_raw)
                if not isinstance(steps, list):
                    logger.error(f"Row {idx} ({cid}) steps_json is not a JSON array")
                    return False
            except Exception as e:
                logger.error(f"Row {idx} ({cid}) has invalid JSON: {e}")
                return False

            if status == "NOT_APPLICABLE" and len(steps) != 0:
                logger.error(f"Row {idx} ({cid}) is NOT_APPLICABLE but has {len(steps)} steps")
                return False

            # Validate each step object
            for step_idx, step in enumerate(steps, 1):
                try:
                    parsed_step = AuditStep.model_validate(step)
                    if parsed_step.step_no != step_idx:
                        logger.error(f"Row {idx} ({cid}) step_no {parsed_step.step_no} != expected {step_idx}")
                        return False
                except Exception as e:
                    logger.error(f"Row {idx} ({cid}) invalid step {step_idx}: {e}")
                    return False

    logger.info(f"Validation PASSED: {output_path} is strictly compliant ({len(rows)} valid rows).")
    return True


def main():
    parser = argparse.ArgumentParser(description="Ghost Data Auditor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser("run", help="Run audit on evaluation cases")
    run_parser.add_argument("--dataset-dir", default="dataset", help="Path to dataset directory")
    run_parser.add_argument("--output", default="output.csv", help="Path to output CSV")
    run_parser.add_argument("--samples", action="store_true", help="Run on sample requests instead of evaluation")

    # validate command
    val_parser = subparsers.add_parser("validate", help="Validate output CSV")
    val_parser.add_argument("--file", default="output.csv", help="Path to output CSV")
    val_parser.add_argument("--expected-rows", type=int, default=518, help="Expected number of data rows")

    args = parser.parse_args()

    if args.command == "run":
        run_audit(dataset_dir=args.dataset_dir, output_path=args.output, use_samples=args.samples)
    elif args.command == "validate":
        success = validate_output(output_path=args.file, expected_rows=args.expected_rows)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

