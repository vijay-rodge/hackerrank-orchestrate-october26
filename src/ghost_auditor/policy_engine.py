"""Policy engine module for applying deletion_rules.csv."""

from typing import Dict, Optional, Tuple
from ghost_auditor.models import DeletionRule
from ghost_auditor.ingestion import DatasetContainer


class PolicyEngine:
    """Evaluates rules from deletion_rules.csv and prescribes treatments."""

    def __init__(self, dataset: DatasetContainer):
        self.rules_by_category: Dict[str, DeletionRule] = {
            r.data_category: r for r in dataset.rules
        }

    def get_required_action(self, data_category: str) -> str:
        rule = self.rules_by_category.get(data_category)
        if rule:
            return rule.required_action
        # Default policy mapping
        if data_category in ("USER_PROFILE", "SECONDARY_IDENTIFIER", "SEARCH_INDEX_ENTRY", "CACHE_ENTRY", "USER_EXPORT", "MARKETING_PROFILE", "SUPPORT_ATTACHMENT"):
            return "DELETE"
        elif data_category in ("SUPPORT_MESSAGE", "EMAIL_DELIVERY_LOG", "ACCOUNT_TOMBSTONE"):
            return "REDACT"
        elif data_category in ("ANALYTICS_PROFILE", "PRODUCT_TELEMETRY"):
            return "ANONYMIZE"
        elif data_category in ("SECURITY_AUDIT_LOG", "LEGAL_HOLD_RECORD", "BACKUP_ARCHIVE"):
            return "RETAIN"
        return "DELETE"

    def evaluate_resource_treatment(
        self,
        system_id: str,
        resource_id: str,
        data_category: str,
        is_present: bool,
        is_redacted: bool = False,
        is_anonymized: bool = False,
        is_active: bool = False,
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Determines compliance.
        Returns: (is_compliant, finding_op, remediation_op, verification_op)
        """
        if data_category == "DATA_FLOW":
            if is_active:
                return False, "REPORT_ACTIVE_DATA_FLOW", "DISABLE_DATA_FLOW", "VERIFY_DATA_FLOW_DISABLED"
            return True, None, None, "VERIFY_DATA_FLOW_DISABLED"

        if data_category == "BACKUP_ARCHIVE":
            if is_active:
                return False, "REPORT_RESTORE_RISK", "BLOCK_RESTORE", "VERIFY_RESTORE_BLOCKED"
            return True, None, None, "VERIFY_RESTORE_BLOCKED"

        action = self.get_required_action(data_category)

        if action == "DELETE":
            if is_present:
                return False, "REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"
            return True, None, None, "VERIFY_RECORD_ABSENT"

        elif action == "REDACT":
            if not is_redacted:
                return False, "REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED"
            return True, None, None, "VERIFY_RECORD_REDACTED"

        elif action == "ANONYMIZE":
            if not is_anonymized:
                return False, "REPORT_EXPOSED_PII", "ANONYMIZE_RECORD", "VERIFY_RECORD_ANONYMIZED"
            return True, None, None, "VERIFY_RECORD_ANONYMIZED"

        elif action == "RETAIN":
            if is_present:
                return True, None, None, "VERIFY_RECORD_PRESENT"
            return False, "REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_PRESENT"

        return True, None, None, "VERIFY_RECORD_ABSENT"

