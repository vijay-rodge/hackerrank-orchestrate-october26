"""Validated Pydantic data models for Ghost Data Auditor."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from ghost_auditor.config import (
    ALLOWED_STATUSES,
    PHASE_ORDER,
    ALLOWED_OP_STATE,
)


class DeletionRequest(BaseModel):
    case_id: str
    email: str
    requested_at: str
    reported_status: str
    reported_at: str
    audit_at: str
    request_text: str


class UserIdentity(BaseModel):
    user_id: str
    name: str
    email: str
    phone: str
    email_hash: str
    updated_at: str


class AuditLogEntry(BaseModel):
    audit_id: str
    user_id: str
    event_time: str
    field_name: str
    old_value: str
    new_value: str


class SystemActivity(BaseModel):
    activity_id: str
    event_time: str
    event_type: str
    source_system: str
    target_system: str
    resource_id: str
    reported_result: str
    details: str


class DeletionRule(BaseModel):
    rule_id: str
    data_category: str
    condition: str
    required_action: str


class EvidenceFile(BaseModel):
    file_id: str
    file_path: str
    origin: str
    captured_at: str


class AuditStep(BaseModel):
    step_no: int = Field(..., ge=1)
    phase: str
    system_id: str
    resource_id: str
    operation: str
    state: str
    evidence_id: str = ""

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, v: str) -> str:
        if v not in PHASE_ORDER:
            raise ValueError(f"Invalid phase: {v}. Must be one of {list(PHASE_ORDER.keys())}")
        return v

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, v: str) -> str:
        if v not in ALLOWED_OP_STATE:
            raise ValueError(f"Invalid operation: {v}")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str, info) -> str:
        op = info.data.get("operation")
        if op and op in ALLOWED_OP_STATE:
            expected_state = ALLOWED_OP_STATE[op]
            if v != expected_state:
                raise ValueError(f"State '{v}' does not match expected state '{expected_state}' for operation '{op}'")
        return v


class CaseAuditResult(BaseModel):
    case_id: str
    deletion_status: str
    steps: List[AuditStep] = Field(default_factory=list)

    @field_validator("deletion_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ALLOWED_STATUSES:
            raise ValueError(f"Invalid deletion_status: {v}. Must be one of {ALLOWED_STATUSES}")
        return v

    @property
    def steps_json(self) -> str:
        import json
        return json.dumps([s.model_dump() for s in self.steps], separators=(",", ":"))
