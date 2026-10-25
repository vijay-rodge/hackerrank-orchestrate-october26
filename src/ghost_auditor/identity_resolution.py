"""Identity resolution module for reconstructing current and historical identifiers."""

from dataclasses import dataclass, field
from typing import Optional, Set
from ghost_auditor.ingestion import DatasetContainer


@dataclass
class ResolvedIdentity:
    user_id: str
    name: str
    current_email: str
    emails: Set[str] = field(default_factory=set)
    phones: Set[str] = field(default_factory=set)
    email_hashes: Set[str] = field(default_factory=set)
    resolution_method: str = "direct"  # direct, audit, or unresolved


class IdentityResolver:
    """Resolves request identifiers against current and historical snapshots."""

    def __init__(self, dataset: DatasetContainer):
        self.dataset = dataset

    def resolve(self, request_email: str) -> Optional[ResolvedIdentity]:
        req_email_clean = request_email.strip().lower()

        user_id = None
        method = "direct"

        # 1. Match current identity snapshot
        if req_email_clean in self.dataset.identities_by_email:
            ident = self.dataset.identities_by_email[req_email_clean]
            user_id = ident.user_id
        # 2. Match historical audit log
        elif req_email_clean in self.dataset.audit_email_to_uid:
            user_id = self.dataset.audit_email_to_uid[req_email_clean]
            method = "audit"

        if not user_id or user_id not in self.dataset.identities_by_uid:
            return None

        ident = self.dataset.identities_by_uid[user_id]
        resolved = ResolvedIdentity(
            user_id=user_id,
            name=ident.name,
            current_email=ident.email,
            resolution_method=method,
        )

        resolved.emails.add(ident.email.strip().lower())
        resolved.emails.add(req_email_clean)
        if ident.phone:
            resolved.phones.add(ident.phone.strip())
        if ident.email_hash:
            resolved.email_hashes.add(ident.email_hash.strip().lower())

        # Collect historical changes from audit log
        audit_entries = self.dataset.audit_logs_by_uid.get(user_id, [])
        for entry in audit_entries:
            if entry.field_name == "email":
                if entry.old_value:
                    resolved.emails.add(entry.old_value.strip().lower())
                if entry.new_value:
                    resolved.emails.add(entry.new_value.strip().lower())
            elif entry.field_name == "phone":
                if entry.old_value:
                    resolved.phones.add(entry.old_value.strip())
                if entry.new_value:
                    resolved.phones.add(entry.new_value.strip())
            elif entry.field_name == "email_hash":
                if entry.old_value:
                    resolved.email_hashes.add(entry.old_value.strip().lower())
                if entry.new_value:
                    resolved.email_hashes.add(entry.new_value.strip().lower())

        return resolved

