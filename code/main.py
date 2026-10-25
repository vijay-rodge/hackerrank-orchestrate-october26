"""
HackerRank Orchestrate: Ghost Data Still Exists
Main solution entry point.

Runs the complete AI data deletion audit pipeline over dataset/deletion_requests.csv
and generates the authoritative output.csv at the repository root.
"""

import sys
import os
import time

# Ensure src/ is on sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(repo_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from ghost_auditor.ingestion import DatasetContainer
from ghost_auditor.pipeline import DeletionAuditorPipeline
from ghost_auditor.cli import validate_output


def main():
    print("=" * 70)
    print("HackerRank Orchestrate: Ghost Data Still Exists")
    print("AI-Powered Data Deletion Audit & Remediation Verification Pipeline")
    print("=" * 70)

    start_time = time.time()
    dataset_dir = os.path.join(repo_root, "dataset")
    output_path = os.path.join(repo_root, "output.csv")

    print(f"\n[1/4] Ingesting datasets from: {dataset_dir} ...")
    dataset = DatasetContainer(dataset_dir)
    print(f"      Loaded {len(dataset.requests)} evaluation requests.")
    print(f"      Loaded {len(dataset.identities)} user identity snapshots.")
    print(f"      Loaded {len(dataset.audit_logs)} identity audit log entries.")
    print(f"      Loaded {len(dataset.activities)} system activity events.")
    print(f"      Loaded {len(dataset.rules)} policy deletion rules.")
    print(f"      Loaded {len(dataset.evidence_manifest)} evidence files in manifest.")

    print("\n[2/4] Initializing evidence inventory and extractors ...")
    pipeline = DeletionAuditorPipeline(dataset)
    print(f"      Evidence extractor indexed {len(pipeline.extractor.cached_facts)} evidence sources.")

    print(f"\n[3/4] Running audit pipeline across {len(dataset.requests)} cases ...")
    results = pipeline.run_all(dataset.requests)
    print(f"      Completed auditing {len(results)} cases.")

    # Status summary
    complete_count = sum(1 for r in results if r.deletion_status == "COMPLETE")
    incomplete_count = sum(1 for r in results if r.deletion_status == "INCOMPLETE")
    na_count = sum(1 for r in results if r.deletion_status == "NOT_APPLICABLE")
    print(f"      Status distribution:")
    print(f"        - COMPLETE:       {complete_count}")
    print(f"        - INCOMPLETE:     {incomplete_count}")
    print(f"        - NOT_APPLICABLE: {na_count}")

    print(f"\n[4/4] Writing output CSV to: {output_path} ...")
    pipeline.write_output_csv(results, output_path)

    # Validate output
    is_valid = validate_output(output_path, expected_rows=518)
    elapsed = time.time() - start_time

    if is_valid:
        print(f"\nSUCCESS: Generated {output_path} with 518 verified cases in {elapsed:.2f}s.")
        sys.exit(0)
    else:
        print(f"\nERROR: Output validation failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()

