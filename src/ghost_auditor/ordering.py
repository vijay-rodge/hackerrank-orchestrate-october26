"""Strict step ordering and normalization module."""

from typing import List
from ghost_auditor.models import AuditStep
from ghost_auditor.config import (
    PHASE_ORDER,
    OPERATION_ORDER,
)


def sort_and_renumber_steps(steps: List[AuditStep]) -> List[AuditStep]:
    """
    Sorts steps strictly by:
    1. Phase: FINDING (1) -> REMEDIATION (2) -> VERIFICATION (3)
    2. Operation order within phase (defined by specification)
    3. system_id ascending
    4. resource_id ascending
    Renumbering consecutively starting at 1.
    """
    def sort_key(s: AuditStep):
        p_idx = PHASE_ORDER.get(s.phase, 99)
        o_idx = OPERATION_ORDER.get((s.phase, s.operation), 99)
        return (p_idx, o_idx, s.system_id, s.resource_id)

    sorted_steps = sorted(steps, key=sort_key)
    renumbered = []
    for idx, s in enumerate(sorted_steps, 1):
        renumbered.append(
            AuditStep(
                step_no=idx,
                phase=s.phase,
                system_id=s.system_id,
                resource_id=s.resource_id,
                operation=s.operation,
                state=s.state,
                evidence_id=s.evidence_id,
            )
        )
    return renumbered

