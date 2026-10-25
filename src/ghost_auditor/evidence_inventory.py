"""Evidence inventory module for verifying and indexing supplied evidence files."""

import csv
import os
from pathlib import Path
from typing import Dict, List, Optional
from ghost_auditor.models import EvidenceFile
from ghost_auditor.config import DATASET_DIR, EVIDENCE_DIR


class EvidenceInventory:
    """Manages the manifest and filesystem inventory of all 94 evidence files."""

    def __init__(self, dataset_dir: Path = DATASET_DIR):
        self.dataset_dir = Path(dataset_dir)
        self.evidence_dir = self.dataset_dir / "evidence"
        self.manifest: Dict[str, EvidenceFile] = {}
        self.files_by_origin: Dict[str, List[EvidenceFile]] = {}
        self.resolved_paths: Dict[str, Path] = {}

        self._load_manifest()

    def _load_manifest(self):
        manifest_path = self.dataset_dir / "evidence_files.csv"
        if not manifest_path.exists():
            return

        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ev = EvidenceFile(**row)
                self.manifest[ev.file_id] = ev
                self.files_by_origin.setdefault(ev.origin, []).append(ev)

                # Resolve actual file path
                p1 = self.dataset_dir / ev.file_path
                p2 = self.dataset_dir.parent / ev.file_path
                if p1.exists():
                    self.resolved_paths[ev.file_id] = p1
                elif p2.exists():
                    self.resolved_paths[ev.file_id] = p2

    def get_file_path(self, file_id: str) -> Optional[Path]:
        return self.resolved_paths.get(file_id)

    def get_evidence(self, file_id: str) -> Optional[EvidenceFile]:
        return self.manifest.get(file_id)

    def get_files_at_or_before(self, cutoff_iso: str) -> List[EvidenceFile]:
        """Returns evidence files captured at or before the given cutoff timestamp."""
        eligible = []
        for ev in self.manifest.values():
            if ev.captured_at <= cutoff_iso:
                eligible.append(ev)
        return sorted(eligible, key=lambda x: x.captured_at)

