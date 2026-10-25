"""
Runner script for Deletion Audit.
"""

import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, "src"))

from ghost_auditor.cli import run_audit

if __name__ == "__main__":
    dataset_dir = os.path.join(repo_root, "dataset")
    output_path = os.path.join(repo_root, "output.csv")
    run_audit(dataset_dir=dataset_dir, output_path=output_path)

