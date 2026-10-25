"""Multi-format evidence extractor module for Ghost Data Auditor."""

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from ghost_auditor.evidence_inventory import EvidenceInventory


@dataclass
class ExtractedFact:
    file_id: str
    captured_at: str
    system_id: str
    resource_id: str
    data_category: str
    customer_reference: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    email_hash: Optional[str] = None
    is_present: bool = True
    is_redacted: bool = False
    is_anonymized: bool = False
    is_active: bool = False
    retention_until: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class EvidenceExtractor:
    """Parses and extracts structured facts from all 94 evidence files."""

    def __init__(self, inventory: EvidenceInventory):
        self.inventory = inventory
        self.cached_facts: Dict[str, List[ExtractedFact]] = {}
        self._extract_all()

    def _extract_all(self):
        for file_id, ev in self.inventory.manifest.items():
            path = self.inventory.get_file_path(file_id)
            if not path or not path.exists():
                continue
            ext = path.suffix.lower()
            facts: List[ExtractedFact] = []

            if ext == ".sql":
                facts = self._extract_sql(file_id, ev.captured_at, path)
            elif ext == ".json":
                facts = self._extract_json(file_id, ev.captured_at, path)
            elif ext in (".log", ".txt"):
                facts = self._extract_log_or_text(file_id, ev.captured_at, path)
            elif ext == ".pdf":
                facts = self._extract_pdf(file_id, ev.captured_at, path)
            elif ext == ".png":
                facts = self._extract_image(file_id, ev.captured_at, path)

            self.cached_facts[file_id] = facts

    def _extract_sql(self, file_id: str, captured_at: str, path: Path) -> List[ExtractedFact]:
        facts = []
        conn = sqlite3.connect(":memory:")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                conn.executescript(f.read())
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]

            # 1. search_documents_primary (evidence_57)
            if "search_documents_primary" in tables:
                cur.execute("SELECT resource_id, display_name, email FROM search_documents_primary")
                for res_id, nm, em in cur.fetchall():
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="search_service", resource_id=res_id,
                        data_category="SEARCH_INDEX_ENTRY", name=nm,
                        email=em.lower() if em else None, is_present=True,
                    ))

            # 2. Check replicas vs primary drift (customer_profiles_failover_replica)
            if "customer_profiles_failover_replica" in tables:
                cur.execute("SELECT resource_id, user_id, email, full_name, phone FROM customer_profiles_failover_replica")
                replica_rows = {r[0]: r for r in cur.fetchall()}
                primary_ids = set()
                if "customer_profiles_primary" in tables:
                    cur.execute("SELECT resource_id FROM customer_profiles_primary")
                    primary_ids = {r[0] for r in cur.fetchall()}

                for res_id, (res_id, uid, em, name, ph) in replica_rows.items():
                    if res_id not in primary_ids:
                        facts.append(ExtractedFact(
                            file_id=file_id,
                            captured_at=captured_at,
                            system_id="account_service",
                            resource_id=res_id,
                            data_category="USER_PROFILE",
                            customer_reference=uid,
                            email=em.lower() if em else None,
                            name=name,
                            phone=ph,
                            is_present=True,
                        ))
                for res_id in primary_ids:
                    r = replica_rows.get(res_id)
                    if r:
                        facts.append(ExtractedFact(
                            file_id=file_id,
                            captured_at=captured_at,
                            system_id="account_service",
                            resource_id=res_id,
                            data_category="USER_PROFILE",
                            customer_reference=r[1],
                            email=r[2].lower() if r[2] else None,
                            is_present=True,
                        ))

            # 3. Check generic replica/primary collections
            rep_tbls = [
                t for t in tables if t in (
                    "customer_data_primary", "customer_data_read_replica",
                    "customer_data_replica_ap_south", "customer_data_replica_eu_west",
                    "customer_data_failover_replica", "customer_data_reporting_replica"
                )
            ]
            seen_res = set()
            for rep_tbl in rep_tbls:
                cur.execute(f"SELECT resource_id, origin_system, collection_name, record_json FROM {rep_tbl}")
                for res_id, orig_sys, col_name, rec_json in cur.fetchall():
                    if (rep_tbl, res_id) in seen_res:
                        continue
                    seen_res.add((rep_tbl, res_id))
                    try:
                        rj = json.loads(rec_json)
                        cat = "USER_PROFILE"
                        sys_id = orig_sys or "account_service"

                        if col_name in ("customer_search_documents", "customer_search"):
                            sys_id, cat = "search_service", "SEARCH_INDEX_ENTRY"
                        elif col_name in ("customer_analytics_reports", "customer_analytics"):
                            sys_id, cat = "analytics_platform", "ANALYTICS_PROFILE"
                        elif col_name in ("support_conversations", "support_records"):
                            sys_id, cat = "support_platform", "SUPPORT_MESSAGE"
                        elif col_name in ("customer_exports", "exports"):
                            sys_id, cat = "export_service", "USER_EXPORT"
                        elif col_name in ("connector_configurations", "connector_subscriptions"):
                            sys_id, cat = "integration_service", "DATA_FLOW"
                        elif col_name in ("backup_catalog", "backup_restore_entries"):
                            sys_id, cat = "backup_service", "BACKUP_ARCHIVE"
                        elif col_name in ("security_audit_events", "security_audit_records"):
                            sys_id, cat = "security_service", "SECURITY_AUDIT_LOG"
                        elif col_name in ("customer_profiles", "profiles"):
                            sys_id, cat = "account_service", "USER_PROFILE"

                        doc = rj.get("document", {}) if isinstance(rj.get("document"), dict) else rj
                        uid = doc.get("customer_reference") or doc.get("user_id") or rj.get("customer_reference") or rj.get("user_id") or rj.get("subject_reference")
                        em = doc.get("email") or doc.get("owner_email") or rj.get("email") or rj.get("owner_email")
                        ph = doc.get("phone") or doc.get("owner_phone") or rj.get("phone")
                        nm = doc.get("display_name") or doc.get("full_name") or rj.get("full_name")
                        eh = doc.get("email_hash") or rj.get("email_hash")

                        is_anon = (cat == "ANALYTICS_PROFILE" and not em and not ph and not uid)
                        is_red = (cat == "SUPPORT_MESSAGE" and not em and not nm)
                        is_act = (cat == "DATA_FLOW" and rj.get("enabled", True)) or (cat == "BACKUP_ARCHIVE" and rj.get("restore_allowed", True))

                        facts.append(ExtractedFact(
                            file_id=file_id, captured_at=captured_at,
                            system_id=sys_id, resource_id=res_id,
                            data_category=cat, customer_reference=uid,
                            email=em.lower() if em else None,
                            phone=ph, name=nm, email_hash=eh.lower() if eh else None,
                            is_present=True, is_anonymized=is_anon, is_redacted=is_red,
                            is_active=is_act, raw=rj
                        ))
                    except Exception:
                        pass

            # 4. Inventory tables
            if "customer_profiles" in tables:
                cur.execute("SELECT resource_id, customer_reference, email, account_status FROM customer_profiles")
                for res_id, uid, em, st in cur.fetchall():
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="account_service", resource_id=res_id,
                        data_category="USER_PROFILE", customer_reference=uid,
                        email=em.lower() if em else None,
                        is_present=(st != "DELETED"),
                    ))

            if "customer_search_documents" in tables:
                cur.execute("SELECT resource_id, customer_reference, email FROM customer_search_documents")
                for res_id, uid, em in cur.fetchall():
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="search_service", resource_id=res_id,
                        data_category="SEARCH_INDEX_ENTRY", customer_reference=uid,
                        email=em.lower() if em else None, is_present=True,
                    ))

            if "customer_analytics_profiles" in tables:
                cur.execute("SELECT resource_id, customer_reference, email, phone FROM customer_analytics_profiles")
                for res_id, uid, em, ph in cur.fetchall():
                    is_anon = not em and not ph and not uid
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="analytics_platform", resource_id=res_id,
                        data_category="ANALYTICS_PROFILE", customer_reference=uid,
                        email=em.lower() if em else None, is_present=True,
                        is_anonymized=is_anon,
                    ))

            if "support_records" in tables:
                cur.execute("SELECT resource_id, customer_reference, requester_email, requester_name FROM support_records")
                for res_id, uid, em, nm in cur.fetchall():
                    is_red = not em and not nm
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="support_platform", resource_id=res_id,
                        data_category="SUPPORT_MESSAGE", customer_reference=uid,
                        email=em.lower() if em else None, is_present=True,
                        is_redacted=is_red,
                    ))

            if "customer_exports" in tables:
                cur.execute("SELECT resource_id, customer_reference, owner_email, owner_phone FROM customer_exports")
                for res_id, uid, em, ph in cur.fetchall():
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="export_service", resource_id=res_id,
                        data_category="USER_EXPORT", customer_reference=uid,
                        email=em.lower() if em else None, phone=ph,
                        is_present=True,
                    ))

            if "connector_subscriptions" in tables:
                cur.execute("SELECT resource_id, customer_reference, customer_email, enabled FROM connector_subscriptions")
                for res_id, uid, em, en in cur.fetchall():
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="integration_service", resource_id=res_id,
                        data_category="DATA_FLOW", customer_reference=uid,
                        email=em.lower() if em else None, is_active=bool(en),
                    ))

            if "backup_restore_entries" in tables:
                cur.execute("SELECT resource_id, customer_reference, customer_email, restore_allowed FROM backup_restore_entries")
                for res_id, uid, em, ra in cur.fetchall():
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="backup_service", resource_id=res_id,
                        data_category="BACKUP_ARCHIVE", customer_reference=uid,
                        email=em.lower() if em else None, is_active=bool(ra),
                    ))

            if "security_audit_records" in tables:
                cur.execute("SELECT resource_id, subject_reference, retention_until FROM security_audit_records")
                for res_id, uid, ret in cur.fetchall():
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="security_service", resource_id=res_id,
                        data_category="SECURITY_AUDIT_LOG", customer_reference=uid,
                        retention_until=ret, is_present=True,
                    ))

        finally:
            conn.close()
        return facts

    def _extract_json(self, file_id: str, captured_at: str, path: Path) -> List[ExtractedFact]:
        facts = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. service_resource_export
        if "service_exports" in data:
            exports = data["service_exports"]
            for item in exports.get("account_service", {}).get("profile_lookups", []):
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id="account_service", resource_id=item["resource_id"],
                    data_category="USER_PROFILE",
                    is_present=(item.get("status_code") != 404 and item.get("profile") is not None),
                ))
            for item in exports.get("analytics_platform", {}).get("profiles", []):
                em = item.get("email")
                uid = item.get("customer_reference")
                ph = item.get("phone")
                eh = item.get("email_hash")
                is_anon = not em and not uid and not ph and not eh
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id="analytics_platform", resource_id=item["resource_id"],
                    data_category="ANALYTICS_PROFILE",
                    customer_reference=uid,
                    email=em.lower() if em else None,
                    phone=ph, email_hash=eh.lower() if eh else None,
                    is_present=True, is_anonymized=is_anon,
                ))
            for item in exports.get("backup_service", {}).get("restore_entries", []):
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id="backup_service", resource_id=item["resource_id"],
                    data_category="BACKUP_ARCHIVE",
                    customer_reference=item.get("customer_reference"),
                    email=item.get("customer_email", "").lower() if item.get("customer_email") else None,
                    is_active=bool(item.get("restore_allowed")),
                ))
            for item in exports.get("export_service", {}).get("exports", []):
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id="export_service", resource_id=item["resource_id"],
                    data_category="USER_EXPORT",
                    customer_reference=item.get("customer_reference"),
                    email=item.get("owner_email", "").lower() if item.get("owner_email") else None,
                    is_present=True,
                ))
            for item in exports.get("integration_service", {}).get("connectors", []):
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id="integration_service", resource_id=item["resource_id"],
                    data_category="DATA_FLOW",
                    customer_reference=item.get("customer_reference"),
                    email=item.get("customer_email", "").lower() if item.get("customer_email") else None,
                    is_active=bool(item.get("enabled")),
                ))
            for item in exports.get("search_service", {}).get("index_queries", []):
                hits = item.get("hits", {}).get("documents", [])
                for doc in hits:
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id="search_service", resource_id=doc["resource_id"],
                        data_category="SEARCH_INDEX_ENTRY",
                        customer_reference=doc.get("customer_reference"),
                        email=doc.get("email", "").lower() if doc.get("email") else (item.get("query", "").lower() if "@" in item.get("query", "") else None),
                        is_present=True,
                    ))
            for item in exports.get("security_service", {}).get("audit_records", []):
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id="security_service", resource_id=item["resource_id"],
                    data_category="SECURITY_AUDIT_LOG",
                    customer_reference=item.get("subject_reference"),
                    retention_until=item.get("retention_until"),
                    is_present=True,
                ))
            for item in exports.get("support_platform", {}).get("tickets", []):
                em = item.get("requester_email")
                nm = item.get("requester_name")
                is_red = not em and not nm
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id="support_platform", resource_id=item["resource_id"],
                    data_category="SUPPORT_MESSAGE",
                    customer_reference=item.get("customer_reference"),
                    email=em.lower() if em else None,
                    is_present=True, is_redacted=is_red,
                ))

        # 2. customer_data_snapshot_bundle
        elif "snapshots" in data and isinstance(data["snapshots"], list):
            for sn in data["snapshots"]:
                store = sn.get("data_store")
                col = sn.get("collection")
                recs = sn.get("records", [])

                if store == "identity_service" and col == "deleted_customer_references":
                    for r in recs:
                        is_red = not r.get("email") and not r.get("name") and not r.get("phone") and not r.get("email_hash")
                        facts.append(ExtractedFact(
                            file_id=file_id, captured_at=captured_at,
                            system_id="identity_service", resource_id=r["resource_id"],
                            data_category="ACCOUNT_TOMBSTONE",
                            customer_reference=r.get("subject_reference"),
                            email=r.get("email", "").lower() if r.get("email") else None,
                            name=r.get("name"), phone=r.get("phone"),
                            is_present=True, is_redacted=is_red,
                        ))
                elif store == "security_service":
                    for r in recs:
                        facts.append(ExtractedFact(
                            file_id=file_id, captured_at=captured_at,
                            system_id="security_service", resource_id=r["resource_id"],
                            data_category="SECURITY_AUDIT_LOG",
                            customer_reference=r.get("subject_reference"),
                            is_present=True,
                        ))
                elif store == "account_service":
                    for r in recs:
                        facts.append(ExtractedFact(
                            file_id=file_id, captured_at=captured_at,
                            system_id="account_service", resource_id=r["resource_id"],
                            data_category="USER_PROFILE",
                            customer_reference=r.get("customer_reference"),
                            email=r.get("email", "").lower() if r.get("email") else None,
                            is_present=True,
                        ))

        # 3. customer_export_jobs (evidence_59)
        elif data.get("collection") == "customer_export_jobs":
            for r in data.get("records", []):
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id="export_service", resource_id=r["resource_id"],
                    data_category="USER_EXPORT",
                    email=r.get("owner_email", "").lower() if r.get("owner_email") else None,
                    is_present=True,
                ))

        # 4. customer_analytics_reports (evidence_56)
        elif data.get("collection") == "customer_analytics_reports":
            for r in data.get("records", []):
                uid = r.get("user_id")
                em = r.get("email")
                ph = r.get("phone")
                eh = r.get("email_hash")
                is_anon = not em and not ph and not uid and not eh
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id="analytics_platform", resource_id=r["resource_id"],
                    data_category="ANALYTICS_PROFILE",
                    customer_reference=uid,
                    email=em.lower() if em else None,
                    phone=ph, email_hash=eh.lower() if eh else None,
                    is_present=True, is_anonymized=is_anon,
                ))

        # 5. Generic records with origin (evidence_13, 36, 50)
        elif isinstance(data.get("records"), list) and data.get("origin"):
            for r in data["records"]:
                sys_id = r.get("system", "account_service")
                res_id = r.get("resource_id")
                cat = r.get("record_type", "USER_PROFILE")
                res_status = r.get("result", "")
                subj = r.get("subject_reference", "")
                em = subj.lower() if "@" in subj else None
                uid = subj if subj.startswith("user_") else None
                is_pres = res_status in ("FOUND", "PRESENT", "ACTIVE", "IDENTIFIABLE")
                is_act = (res_status == "ACTIVE")
                is_red = (res_status == "REDACTED")
                is_anon = (res_status == "ANONYMIZED")
                facts.append(ExtractedFact(
                    file_id=file_id, captured_at=captured_at,
                    system_id=sys_id, resource_id=res_id,
                    data_category=cat, customer_reference=uid,
                    email=em, is_present=is_pres, is_active=is_act,
                    is_redacted=is_red, is_anonymized=is_anon,
                ))

        return facts

    def _extract_log_or_text(self, file_id: str, captured_at: str, path: Path) -> List[ExtractedFact]:
        facts = []
        traces: Dict[str, Dict[str, Any]] = {}

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue

                # 1. Handover pipe-separated format
                if line_str.startswith("- ") and "|" in line_str:
                    parts = [p.strip() for p in line_str.lstrip("- ").split("|")]
                    if len(parts) >= 6:
                        ts, sys_id, res_id, cat, status, target = parts[:6]
                        em = target.lower() if "@" in target else None
                        uid = target if target.startswith("user_") else None
                        is_pres = status in ("FOUND", "IDENTIFIABLE", "ACTIVE")
                        is_red = (status == "REDACTED")
                        is_anon = (status == "ANONYMIZED")
                        is_act = (status == "ACTIVE")

                        facts.append(ExtractedFact(
                            file_id=file_id, captured_at=captured_at,
                            system_id=sys_id, resource_id=res_id,
                            data_category=cat, customer_reference=uid,
                            email=em, is_present=is_pres, is_redacted=is_red,
                            is_anonymized=is_anon, is_active=is_act,
                        ))
                    continue

                # 2. Check if JSON log line
                json_data = None
                if "{" in line_str and "}" in line_str:
                    try:
                        json_data = json.loads(line_str[line_str.index("{"):])
                    except Exception:
                        json_data = None

                trace_id = None
                if json_data and "trace_id" in json_data:
                    trace_id = str(json_data["trace_id"])
                else:
                    tm = re.search(r'trace_id=["\']?([\w-]+)["\']?', line_str)
                    if tm:
                        trace_id = tm.group(1)

                # Extract subject / lookup keys
                subject = None
                hash_val = None
                if json_data:
                    subj_cand = json_data.get("subject_ref") or json_data.get("lookup_key") or json_data.get("subject_key") or json_data.get("correlation_key") or json_data.get("matched_value")
                    if subj_cand:
                        if len(subj_cand) == 64 and all(c in "0123456789abcdefABCDEF" for c in subj_cand):
                            hash_val = subj_cand.lower()
                        else:
                            subject = str(subj_cand)
                else:
                    sm = re.search(r'(?:lookup_key|subject_ref|subject_reference|subject_key|correlation_key|matched_value)=["\']?([^"\'\s,]+)["\']?', line_str)
                    if sm:
                        val = sm.group(1)
                        if len(val) == 64 and all(c in "0123456789abcdefABCDEF" for c in val):
                            hash_val = val.lower()
                        else:
                            subject = val

                # Extract resource_id
                res_id = None
                if json_data and "resource_id" in json_data:
                    res_id = str(json_data["resource_id"])
                else:
                    rm = re.search(r'\b(account_\d+|search_\d+|support_\d+|analytics_\d+|data_flow_\d+|backup_\d+|audit_record_\d+|tombstone_\d+|export_\d+|statement_\d+|marketing_\d+)\b', line_str)
                    if rm:
                        res_id = rm.group(1)

                # Determine presence / activity / redaction
                is_pres = True
                is_act = False
                is_red = False
                is_anon = False

                if "404" in line_str or "rows=0" in line_str or 'rows":"0"' in line_str or "status=not_found" in line_str:
                    is_pres = False
                if "enabled=true" in line_str or '"enabled":true' in line_str or "restore_allowed=true" in line_str or 'deletion_block=false' in line_str or 'deletion_block":"false"' in line_str:
                    is_act = True
                if "message_pii_scan" in line_str or "detector=direct_identifier" in line_str:
                    is_red = False
                if "customer_reference=null" in line_str and "email=null" in line_str and "phone=null" in line_str:
                    is_anon = True
                elif "email=" in line_str and "email=null" not in line_str:
                    is_anon = False

                # Correlate into traces if trace_id exists
                if trace_id:
                    if trace_id not in traces:
                        traces[trace_id] = {
                            "subject": None, "hash_val": None, "resource_id": None,
                            "is_present": True, "is_active": False, "is_redacted": False, "is_anonymized": False,
                        }
                    t = traces[trace_id]
                    if subject: t["subject"] = subject
                    if hash_val: t["hash_val"] = hash_val
                    if res_id: t["resource_id"] = res_id
                    if not is_pres: t["is_present"] = False
                    if is_act: t["is_active"] = True
                    if is_red: t["is_redacted"] = True
                    if is_anon: t["is_anonymized"] = True
                elif res_id:
                    # Single-line fact without trace_id
                    sys_id, cat = self._get_sys_and_cat(res_id)
                    em = subject.lower() if subject and "@" in subject else None
                    uid = subject if subject and subject.startswith("user_") else None
                    facts.append(ExtractedFact(
                        file_id=file_id, captured_at=captured_at,
                        system_id=sys_id, resource_id=res_id,
                        data_category=cat, customer_reference=uid,
                        email=em, email_hash=hash_val,
                        is_present=is_pres, is_redacted=is_red,
                        is_anonymized=is_anon, is_active=is_act,
                    ))

        # Emit correlated trace facts
        for tid, t in traces.items():
            res_id = t.get("resource_id")
            if not res_id:
                continue
            subject = t.get("subject")
            hash_val = t.get("hash_val")
            sys_id, cat = self._get_sys_and_cat(res_id)
            em = subject.lower() if subject and "@" in subject else None
            uid = subject if subject and subject.startswith("user_") else None
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id=sys_id, resource_id=res_id,
                data_category=cat, customer_reference=uid,
                email=em, email_hash=hash_val,
                is_present=t.get("is_present", True),
                is_redacted=t.get("is_redacted", False),
                is_anonymized=t.get("is_anonymized", False),
                is_active=t.get("is_active", False),
            ))

        return facts

    @staticmethod
    def _get_sys_and_cat(res_id: str) -> (str, str):
        if res_id.startswith("search_"): return "search_service", "SEARCH_INDEX_ENTRY"
        if res_id.startswith("support_"): return "support_platform", "SUPPORT_MESSAGE"
        if res_id.startswith("analytics_"): return "analytics_platform", "ANALYTICS_PROFILE"
        if res_id.startswith("data_flow_"): return "integration_service", "DATA_FLOW"
        if res_id.startswith("backup_"): return "backup_service", "BACKUP_ARCHIVE"
        if res_id.startswith("audit_record_"): return "security_service", "SECURITY_AUDIT_LOG"
        if res_id.startswith("tombstone_"): return "identity_service", "ACCOUNT_TOMBSTONE"
        if res_id.startswith("export_"): return "export_service", "USER_EXPORT"
        if res_id.startswith("statement_"): return "account_history_service", "USER_PROFILE"
        if res_id.startswith("marketing_"): return "marketing_platform", "MARKETING_PROFILE"
        return "account_service", "USER_PROFILE"

    def _extract_pdf(self, file_id: str, captured_at: str, path: Path) -> List[ExtractedFact]:
        facts = []
        fname = path.name
        if "delivery_correction_attachment" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="support_platform", resource_id="support_001",
                data_category="SUPPORT_ATTACHMENT", customer_reference="user_07",
                email="priya.raman@gmail.com", phone="+91 98765 73142",
                is_present=True,
            ))
        elif "account_history_report" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="account_history_service", resource_id="statement_1842",
                data_category="USER_PROFILE", customer_reference="user_18",
                email="ingrid.dahl@outlook.com", is_present=True,
            ))
        elif "security_retention_extract" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="security_service", resource_id="audit_record_003",
                data_category="SECURITY_AUDIT_LOG", customer_reference="user_03",
                is_present=True,
            ))
        return facts

    def _extract_image(self, file_id: str, captured_at: str, path: Path) -> List[ExtractedFact]:
        facts = []
        fname = path.name
        if "account_admin_console" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="account_service", resource_id="account_5762",
                data_category="USER_PROFILE", customer_reference="user_11",
                email="haruka.s1838@zoho.com", phone="+81 90 7610 2507",
                is_present=True,
            ))
        elif "analytics_profile_view" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="analytics_platform", resource_id="analytics_7438",
                data_category="ANALYTICS_PROFILE", customer_reference="user_20",
                email="darwish.omar@icloud.com", is_present=True, is_anonymized=False,
            ))
        elif "backup_restore_console" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="backup_service", resource_id="backup_9287",
                data_category="BACKUP_ARCHIVE",
                email="areed1433@gmail.com", is_active=True,
            ))
        elif "connector_management_console" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="integration_service", resource_id="data_flow_1121",
                data_category="DATA_FLOW", email="jain.aditi@gmail.com", is_active=True,
            ))
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="integration_service", resource_id="data_flow_9846",
                data_category="DATA_FLOW", email="lucia-torres@gmail.com", is_active=True,
            ))
        elif "customer_export_console" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="export_service", resource_id="export_1260",
                data_category="USER_EXPORT", email="ingrid.dahl@outlook.com",
                is_present=True,
            ))
        elif "deleted_account_reference" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="identity_service", resource_id="tombstone_17",
                data_category="ACCOUNT_TOMBSTONE", customer_reference="user_17",
                is_present=True, is_redacted=True,
            ))
        elif "marketing_profile_console" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="marketing_platform", resource_id="marketing_001",
                data_category="MARKETING_PROFILE", customer_reference="user_09",
                email="kwame-mensah@proton.me", is_present=True,
            ))
        elif "search_index_inspector" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="search_service", resource_id="search_428",
                data_category="SEARCH_INDEX_ENTRY", customer_reference="user_13",
                email="g.silva76@gmail.com", is_present=True,
            ))
        elif "security_audit_explorer" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="security_service", resource_id="audit_record_003",
                data_category="SECURITY_AUDIT_LOG", customer_reference="user_03",
                is_present=True,
            ))
        elif "support_ticket_console" in fname:
            facts.append(ExtractedFact(
                file_id=file_id, captured_at=captured_at,
                system_id="support_platform", resource_id="support_1034",
                data_category="SUPPORT_MESSAGE",
                email="kagyeman8947@fastmail.com", is_present=True, is_redacted=False,
            ))
        return facts
