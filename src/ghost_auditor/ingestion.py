"""Data ingestion and validation module for Ghost Data Auditor."""

import csv
import os
from pathlib import Path
from typing import Dict, List, Optional
from ghost_auditor.models import (
    DeletionRequest,
    UserIdentity,
    AuditLogEntry,
    SystemActivity,
    DeletionRule,
    EvidenceFile,
)
from ghost_auditor.config import DATASET_DIR


class DatasetContainer:
    """Holds parsed and indexed dataset tables."""

    def __init__(self, dataset_dir: Path = DATASET_DIR):
        self.dataset_dir = Path(dataset_dir)
        self.requests: List[DeletionRequest] = []
        self.sample_requests: List[DeletionRequest] = []
        self.identities: List[UserIdentity] = []
        self.audit_logs: List[AuditLogEntry] = []
        self.activities: List[SystemActivity] = []
        self.rules: List[DeletionRule] = []
        self.evidence_manifest: List[EvidenceFile] = []

        # Indexes
        self.requests_by_id: Dict[str, DeletionRequest] = {}
        self.identities_by_uid: Dict[str, UserIdentity] = {}
        self.identities_by_email: Dict[str, UserIdentity] = {}
        self.audit_email_to_uid: Dict[str, str] = {}
        self.audit_logs_by_uid: Dict[str, List[AuditLogEntry]] = {}
        self.evidence_by_id: Dict[str, EvidenceFile] = {}
        self.activities_by_resource: Dict[str, List[SystemActivity]] = {}

        self.load_all()

    def load_all(self):
        """Loads and indexes all tables."""
        self._load_requests()
        self._load_sample_requests()
        self._load_identities()
        self._load_audit_logs()
        self._load_activities()
        self._load_rules()
        self._load_evidence_manifest()

    def _load_requests(self):
        path = self.dataset_dir / "deletion_requests.csv"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                req = DeletionRequest(**row)
                self.requests.append(req)
                self.requests_by_id[req.case_id] = req

    def _load_sample_requests(self):
        path = self.dataset_dir / "sample_deletion_requests.csv"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                req = DeletionRequest(**row)
                self.sample_requests.append(req)

    def _load_identities(self):
        path = self.dataset_dir / "user_identities.csv"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ident = UserIdentity(**row)
                self.identities.append(ident)
                self.identities_by_uid[ident.user_id] = ident
                self.identities_by_email[ident.email.strip().lower()] = ident

    def _load_audit_logs(self):
        path = self.dataset_dir / "user_audit_log.csv"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                log = AuditLogEntry(**row)
                self.audit_logs.append(log)
                self.audit_logs_by_uid.setdefault(log.user_id, []).append(log)
                if log.field_name == "email":
                    if log.old_value:
                        self.audit_email_to_uid[log.old_value.strip().lower()] = log.user_id
                    if log.new_value:
                        self.audit_email_to_uid[log.new_value.strip().lower()] = log.user_id

    def _load_activities(self):
        path = self.dataset_dir / "system_activity.csv"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                act = SystemActivity(**row)
                self.activities.append(act)
                self.activities_by_resource.setdefault(act.resource_id, []).append(act)

    def _load_rules(self):
        path = self.dataset_dir / "deletion_rules.csv"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rule = DeletionRule(**row)
                self.rules.append(rule)

    def _load_evidence_manifest(self):
        path = self.dataset_dir / "evidence_files.csv"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ev = EvidenceFile(**row)
                self.evidence_manifest.append(ev)
                self.evidence_by_id[ev.file_id] = ev

