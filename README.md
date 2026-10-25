# HackerRank Orchestrate - October 2026: Ghost Data Still Exists

## Production-Grade AI-Powered Deletion-Audit & Verification Agent

This repository contains the complete, tested, reproducible solution for the **HackerRank Orchestrate** challenge: **Ghost Data Still Exists**.

---

## 1. Challenge & Submission Overview

- **Official Challenge URL:**  
  [https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists](https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists)
- **Problem Statement:** Detect whether a user's personal data was actually deleted across multi-tier production services, failover replicas, search indexes, analytics cohorts, support attachments, and backup archives as of the case's `audit_at` cutoff timestamp.

---

## 2. Benchmark Accuracy & Performance

The solution achieves **100% across all evaluation dimensions** on the official public benchmark (`sample_output.csv`, 32 cases):

| Evaluation Metric | Baseline Result | Current Result | Benchmark Target | Status |
|---|---|---|---|---|
| **Case-Level Status Accuracy** | 84.4% (27/32) | **100.0%** (32/32) | ≥ 80% | **PASS** |
| **Field-Level Accuracy** | 60.7% (586/965) | **100.0%** (965/965) | ≥ 75% | **PASS** |
| **Step-Level Accuracy** | 49.7% (96/193) | **100.0%** (193/193) | ≥ 70% | **PASS** |
| **Sequence-Level Accuracy** | 15.6% (5/32) | **100.0%** (32/32) | High | **PASS** |

### Root-Cause Resolution of Mismatches
1. **`case_06` (SQL Search Indexing):** Added `search_documents_primary` table parser in `_extract_sql`, surfacing un-deleted search index record `search_001` in `evidence_57`.
2. **`case_08` (Export Job Records):** Added `customer_export_jobs` collection parser in `_extract_json`, surfacing un-deleted user export `export_001` in `evidence_59`.
3. **`case_10` (Multi-Line Log Correlation):** Implemented two-pass `trace_id` correlation in `_extract_log_or_text` to link dissociated lookup keys to contact index records (`support_002` in `evidence_61`).
4. **`case_12` (Historical Email Hash Resolution):** Extracted historical SHA-256 email hashes and resolved them against `ResolvedIdentity.email_hashes` (`analytics_9914` in `evidence_01`).
5. **`case_22` (Read-Replica Data Drift):** Eliminated primary-exclusion filtering in `_extract_sql`, extracting un-deleted records present in both primary and read replicas (`search_8911` and `analytics_4440` in `evidence_05`).

---

## 3. Architecture & Pipeline Design

```
                                  [deletion_requests.csv]
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │    1. Authorization Gate      │
                             │ (negative-signal detection)   │
                             └──────────────┬────────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
           [Not Authorized]                                   [Authorized]
                   │                                               │
                   ▼                                               ▼
         NOT_APPLICABLE (`[]`)                       ┌───────────────────────────┐
                                                     │ 2. Identity Resolution    │
                                                     │ (Snapshot + Audit Log)    │
                                                     └─────────────┬─────────────┘
                                                                   │
                                                                   ▼
                                                     ┌───────────────────────────┐
                                                     │ 3. Multi-Format Evidence  │
                                                     │ (SQL, JSON, Log, PDF, PNG)│
                                                     └─────────────┬─────────────┘
                                                                   │
                                                                   ▼
                                                     ┌───────────────────────────┐
                                                     │ 4. Policy Engine          │
                                                     │ (15 Deletion Rules)       │
                                                     └─────────────┬─────────────┘
                                                                   │
                                                                   ▼
                                                     ┌───────────────────────────┐
                                                     │ 5. Synthesis & Ordering   │
                                                     │ (FIND -> REMEDY -> VERIF) │
                                                     └───────────────────────────┘
```

### Key Engineering Innovations
- **Strict Temporal Evidence Bounding:** Filters evidence strictly within the temporal window `requested_at <= captured_at <= audit_at`, preventing historical pre-deletion snapshots from corrupting the audit.
- **Two-Pass Trace ID Correlation:** Observability logs decouple lookup keys from resource states across multiple lines; our parser correlates events by `trace_id` across lines within each log file.
- **Sequential Account Parity Mapping:** Disambiguates account IDs from `system_activity.csv` by matching deletion requests 1-to-1 against account deletion events with matching status parity.
- **Statutory Retention Verification:** Retains security audit logs under Rule `DEL-012` (`VERIFY_RECORD_PRESENT`) and verifies irreversibly anonymized cohorts under Rule `DEL-007` (`VERIFY_RECORD_ANONYMIZED`).
- **Deterministic 3-Tiered Ordering:** Enforces phase ordering (`FINDING` $\rightarrow$ `REMEDIATION` $\rightarrow$ `VERIFICATION`), operation precedence, ascending `system_id` / `resource_id` tie-breaking, and consecutive 1-based step numbering.

---

## 4. Repository Structure

```text
├── code/
│   ├── main.py                     # Primary prediction entry point (generates output.csv)
│   └── evaluation/
│       ├── main.py                 # Evaluation benchmark runner
│       ├── evaluation_report.md    # Case, step, field, and sequence benchmark report
│       └── usage_report.md         # Token usage, latency, and cost accounting report
├── src/
│   └── ghost_auditor/
│       ├── __init__.py
│       ├── ai_adapter.py           # Provider-independent AI & deterministic adapter
│       ├── cli.py                  # CLI interface (run, validate)
│       ├── config.py               # Path and runtime configuration
│       ├── evidence_extractors.py  # Multi-format evidence parsers (SQL, JSON, logs, PDF, images)
│       ├── evidence_inventory.py   # Manifest catalog & temporal bounding
│       ├── identity_resolution.py  # Graph-based user identity resolver
│       ├── ingestion.py            # Typed dataset ingestion
│       ├── models.py               # Pydantic data schemas
│       ├── ordering.py             # Deterministic step sorter
│       ├── pipeline.py             # Core audit pipeline
│       └── policy_engine.py        # 15 Deletion rules policy engine
├── tests/
│   ├── test_audit_engine.py        # Integration tests on pipeline execution
│   ├── test_cli.py                 # CLI interface tests
│   ├── test_identity.py            # Identity resolution tests
│   └── test_regression_mismatches.py # Targeted regression tests for cases 06, 08, 10, 12, 22
├── scripts/
│   └── package_submission.py       # Submission packager (creates code.zip)
├── evaluation/
│   ├── evaluation_report.md        # Evaluator benchmark report
│   └── usage_report.md             # Token and runtime cost report
├── dataset/                        # Participant-facing datasets & evidence files
├── output.csv                      # Canonical 518-case prediction output
├── code.zip                        # Packaged submission archive (code, prompts, README, reports)
├── log.txt                         # Session turn log complying with AGENTS.md
├── AGENTS.md                       # Master coding agent guidelines & rules
└── README.md                       # Project documentation (this file)
```

---

## 5. Quick Start & Execution Runbook

### Prerequisites
- Python 3.12+ (tested on Python 3.13)
- Install dependencies and the local package:
  ```bash
  pip install -r requirements.txt
  pip install -e .
  ```

### 1. Generate `output.csv` (Primary Entry Point)
To execute the deletion audit across all 518 evaluation requests:
```bash
python code/main.py
```
This produces `output.csv` at the repository root, containing exactly 518 data rows sorted by `case_id` ascending.

### 2. Run Evaluation Benchmark
To run the evaluation suite against ground truth (`sample_output.csv`) and edge cases:
```bash
python code/evaluation/main.py
```
This updates both:
- `evaluation/evaluation_report.md`
- `evaluation/usage_report.md`

### 3. Run Automated Tests
Execute the comprehensive test suite (15 tests covering unit, integration, and regression suites):
```bash
pytest tests -v
```

### 4. Validate `output.csv`
Validate schema and format compliance using the CLI:
```bash
ghost-auditor validate --file output.csv --expected-rows 518
```
or directly via Python:
```bash
python -c "import sys; sys.path.insert(0, 'src'); from ghost_auditor.cli import main; sys.argv = ['ghost_auditor', 'validate', '--file', 'output.csv', '--expected-rows', '518']; main()"
```

### 5. Package Submission Archive (`code.zip`)
To package all source code, configurations, prompts, and reports into `code.zip`:
```bash
python scripts/package_submission.py
```
The script automatically packages all necessary files while strictly excluding `dataset/`, `log.txt`, virtual environments, and caches.

---

## 6. Submission Artifacts Checklist

| Item | Location | Specification |
|---|---|---|
| **Prediction Output** | `output.csv` | Exactly 518 rows, sorted ascending by `case_id`, valid JSON steps |
| **Submission Archive** | `code.zip` | Clean bundle of runnable code, configs, tests, prompts, and evaluation reports |
| **Evaluation Report** | `evaluation/evaluation_report.md` | Detailed 100% metrics across status, step, field, and sequence + 3 custom cases |
| **Usage Report** | `evaluation/usage_report.md` | Accounting of model calls, tokens, latency (0.64s full run), and cost ($0.00) |
| **Audit Log** | `log.txt` | Complete turn-by-turn trace obeying `AGENTS.md` format |
