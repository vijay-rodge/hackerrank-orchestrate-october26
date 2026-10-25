"""
Packaging utility to generate code.zip for HackerRank Orchestrate submission.
"""

import os
import sys
import zipfile
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("package_submission")

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCLUDE_DIRS = {
    ".git", ".pytest_cache", "__pycache__", "dataset", ".gemini", "brain",
    ".vscode", ".idea", "node_modules", "venv", ".env"
}

EXCLUDE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".zip", ".tar", ".gz"
}

EXCLUDE_FILES = {
    "output.csv", ".env", "log.txt"
}


def create_submission_zip(output_zip: str = "code.zip"):
    zip_path = os.path.join(repo_root, output_zip)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    logger.info(f"Creating submission package at: {zip_path}")
    count = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(repo_root):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]

            rel_root = os.path.relpath(root, repo_root)
            if rel_root.startswith("dataset") or rel_root.startswith(".git") or "brain" in rel_root:
                continue

            for f in files:
                if f in EXCLUDE_FILES or any(f.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                    continue
                # Do not package nested archives or secrets
                if f.startswith(".env"):
                    continue

                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, repo_root)
                zipf.write(full_path, rel_path)
                count += 1

    file_size_kb = os.path.getsize(zip_path) / 1024
    logger.info(f"Successfully created {output_zip} with {count} files ({file_size_kb:.1f} KB).")


if __name__ == "__main__":
    create_submission_zip()

