"""
Runner script for Evaluation Suite.
"""

import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, "code"))

from evaluation.main import main

if __name__ == "__main__":
    main()

