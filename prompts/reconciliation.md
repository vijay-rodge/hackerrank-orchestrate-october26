# Prompt Template: Multi-Modal Evidence Reconciliation & Audit Decision

You are a senior data governance architect verifying compliance of deletion workflows against enterprise policy rules.

## Context
A data subject submitted a request under privacy regulations. The internal deletion workflow claims a status of `COMPLETE`, `PARTIALLY_COMPLETE`, or `NOT_STARTED`. However, system logs, replica databases, handover documents, and backup configurations establish the actual state at the `audit_at` cutoff timestamp.

## Instructions
1. **Verify Authorization**:
   - Confirm whether `request_text` actually authorizes permanent account erasure.
   - If the request is for access, rectification, portability export, or marketing opt-out, classify as `NOT_APPLICABLE` and emit an empty step sequence `[]`.
2. **Reconcile Conflicting Evidence**:
   - Replicas: Primary database status does not guarantee failover replica synchronization. Compare primary and regional replicas at `audit_at`.
   - Caches & Search Indexes: Ensure search tokens and cache keys have been purged.
   - Tombstones: Confirm account tombstones contain ONLY permitted internal references (`user_id`), with name, email, phone, and email hash fully redacted.
   - Retained Records: Confirm statutory security audit logs are retained (`VERIFY_RECORD_PRESENT`).
3. **Remediation & Verification Sequencing**:
   - If incomplete, first disable active data flows, then block restore paths, then remediate individual records (delete, redact, anonymize).
   - Order steps strictly: `FINDING` -> `REMEDIATION` -> `VERIFICATION`.

