"""
Runner script for Output Validation.
"""

import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, "src"))

from ghost_auditor.cli import validate_output

if __name__ == "__main__":
    output_path = os.path.join(repo_root, "output.csv")
    is_valid = validate_output(output_path=output_path, expected_rows=518)
    sys.exit(0 if is_valid else 1)

