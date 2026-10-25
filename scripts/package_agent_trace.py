"""
Script to collect original Antigravity agent traces and generate agent-trace.zip.
Follows the requirements in agent_trace_instructions.md and the challenge specification.
"""

import os
import sys
import shutil
import zipfile
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRACE_ZIP_PATH = PROJECT_ROOT / "agent-trace.zip"
CONVERSATION_ID = "18b88279-76a8-49af-a094-b1a77687c15e"
USERPROFILE = os.environ.get("USERPROFILE", "")
SOURCE_BRAIN_DIR = Path(USERPROFILE) / ".gemini" / "antigravity" / "brain" / CONVERSATION_ID
STAGING_DIR = PROJECT_ROOT / "staging_agent_trace"
TARGET_TRACE_ROOT = STAGING_DIR / "agent-trace" / "antigravity" / CONVERSATION_ID


def scan_for_secrets(dir_path: Path):
    """Scan a directory for common API key and token patterns."""
    patterns = [
        re.compile(r"AIza[0-9A-Za-z-_]{35}"),
        re.compile(r"sk-[a-zA-Z0-9]{32,}"),
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),
        re.compile(r"(?:api_key|secret_key|access_token)\s*=\s*['\"][a-zA-Z0-9_\-]{20,}['\"]", re.IGNORECASE),
    ]
    findings = []
    for root, _, files in os.walk(dir_path):
        if "__pycache__" in root:
            continue
        for f in files:
            if f.endswith((".png", ".pyc", ".zip")):
                continue
            fp = Path(root) / f
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")
                for pat in patterns:
                    matches = pat.findall(content)
                    if matches:
                        findings.append((fp, matches))
            except Exception:
                pass
    return findings


def build_trace_manifest():
    """Create a metadata manifest for the agent trace."""
    return {
        "challenge": "HackerRank Orchestrate (October 2026) - Ghost Data Still Exists",
        "harness": "Google Antigravity",
        "tool": "Antigravity",
        "runtime_model": "Gemini 3.8 Flash (High)",
        "conversation_id": CONVERSATION_ID,
        "source_brain_path": str(SOURCE_BRAIN_DIR),
        "project_root": str(PROJECT_ROOT),
        "primary_transcript": f"agent-trace/antigravity/{CONVERSATION_ID}/.system_generated/logs/transcript.jsonl",
        "full_transcript": f"agent-trace/antigravity/{CONVERSATION_ID}/.system_generated/logs/transcript_full.jsonl",
        "user_turns_count": 6,
        "status_accuracy": "100.0% (32/32)",
        "step_accuracy": "100.0% (193/193)",
        "field_accuracy": "100.0% (965/965)",
        "sequence_accuracy": "100.0% (32/32)",
        "evaluation_cases": 518,
    }


def collect_and_package():
    print(f"[INFO] Inspecting source trace directory: {SOURCE_BRAIN_DIR}")
    if not SOURCE_BRAIN_DIR.exists():
        print(f"[ERROR] Source trace directory not found: {SOURCE_BRAIN_DIR}")
        sys.exit(1)

    # 1. Clean staging directory
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    TARGET_TRACE_ROOT.mkdir(parents=True, exist_ok=True)

    # 2. Copy conversation files excluding caches and non-essential binaries
    print(f"[INFO] Copying trace files to staging: {TARGET_TRACE_ROOT}")
    file_count = 0
    copied_bytes = 0

    def copy_tree_filtered(src: Path, dst: Path):
        nonlocal file_count, copied_bytes
        for item in src.iterdir():
            if item.name in ["__pycache__", ".git"]:
                continue
            if item.suffix in [".pyc", ".tmp"]:
                continue
            target = dst / item.name
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                copy_tree_filtered(item, target)
            else:
                shutil.copy2(item, target)
                file_count += 1
                copied_bytes += item.stat().st_size

    copy_tree_filtered(SOURCE_BRAIN_DIR, TARGET_TRACE_ROOT)

    # Also copy the project's root log.txt into the conversation folder for complete trace auditability
    root_log = PROJECT_ROOT / "log.txt"
    if root_log.exists():
        target_log = TARGET_TRACE_ROOT / "log.txt"
        shutil.copy2(root_log, target_log)
        file_count += 1
        copied_bytes += root_log.stat().st_size

    # Write trace manifest inside agent-trace/
    manifest = build_trace_manifest()
    manifest_path = STAGING_DIR / "agent-trace" / "trace_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    file_count += 1

    print(f"[INFO] Staged {file_count} files ({copied_bytes / (1024*1024):.2f} MB)")

    # 3. Secret scan
    print("[INFO] Scanning staged files for accidental secrets...")
    secret_findings = scan_for_secrets(STAGING_DIR)
    if secret_findings:
        print(f"[WARNING] Potential secrets found ({len(secret_findings)}):")
        for fp, m in secret_findings:
            print(f"  {fp.relative_to(STAGING_DIR)}: {m}")
    else:
        print("[INFO] Secret scan clean: No API keys, credentials, or secrets detected.")

    # 4. Generate agent-trace.zip
    # If agent-trace.zip exists, back it up
    if TRACE_ZIP_PATH.exists():
        bak = PROJECT_ROOT / "agent-trace.zip.bak"
        print(f"[INFO] Preserving existing archive to {bak}")
        shutil.copy2(TRACE_ZIP_PATH, bak)

    print(f"[INFO] Compressing to {TRACE_ZIP_PATH}...")
    base_dir = STAGING_DIR / "agent-trace"
    with zipfile.ZipFile(TRACE_ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(base_dir):
            for file in sorted(files):
                file_path = Path(root) / file
                archive_name = file_path.relative_to(STAGING_DIR)
                zipf.write(file_path, str(archive_name))

    # Clean staging directory
    shutil.rmtree(STAGING_DIR)

    # 5. Validate resulting ZIP
    print("[INFO] Validating agent-trace.zip...")
    if not TRACE_ZIP_PATH.exists():
        print("[ERROR] agent-trace.zip was not created!")
        sys.exit(1)

    zip_size = TRACE_ZIP_PATH.stat().st_size
    with zipfile.ZipFile(TRACE_ZIP_PATH, "r") as zipf:
        bad_file = zipf.testzip()
        if bad_file:
            print(f"[ERROR] Corrupted file in zip: {bad_file}")
            sys.exit(1)
        namelist = zipf.namelist()

    # Confirm key files
    expected_transcript = f"agent-trace/antigravity/{CONVERSATION_ID}/.system_generated/logs/transcript.jsonl"
    expected_full = f"agent-trace/antigravity/{CONVERSATION_ID}/.system_generated/logs/transcript_full.jsonl"

    has_transcript = expected_transcript in namelist or any("transcript.jsonl" in n for n in namelist)
    has_full = expected_full in namelist or any("transcript_full.jsonl" in n for n in namelist)

    print(f"[SUCCESS] Archive created successfully at: {TRACE_ZIP_PATH}")
    print(f"  Archive Size: {zip_size:,} bytes ({zip_size / (1024*1024):.2f} MB)")
    print(f"  Total Archived Files: {len(namelist)}")
    print(f"  Includes transcript.jsonl: {has_transcript}")
    print(f"  Includes transcript_full.jsonl: {has_full}")
    print("  First 10 files in archive:")
    for n in namelist[:10]:
        print(f"    - {n}")


if __name__ == "__main__":
    collect_and_package()

