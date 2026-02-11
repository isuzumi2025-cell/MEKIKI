# Task Model v2

Status: Active  
Last Updated: 2026-02-11

## 1. Purpose

Define a stable task schema for autonomous orchestration with security and
governance metadata.

## 2. Canonical Task Schema

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Literal

RiskClass = Literal["LOW", "MEDIUM", "HIGH"]
TaskStatus = Literal[
    "pending", "ready", "in_progress", "verifying",
    "blocked", "failed", "completed", "quarantined"
]
AgentRole = Literal["implementer", "investigator", "verifier", "refactorer"]

@dataclass
class Task:
    task_id: str
    title: str
    description: str
    risk_class: RiskClass
    status: TaskStatus
    assigned_to: AgentRole
    acceptance_criteria: List[str] = field(default_factory=list)
    security_controls: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    touched_files: List[str] = field(default_factory=list)
    approvals_required: int = 1
    approvals_granted: int = 0
    verifier_status: Optional[str] = None
    incident_flag: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
```

## 3. Role Responsibilities

- implementer: change code and tests within scoped task boundaries.
- investigator: perform root-cause analysis and containment strategy.
- verifier: run checks and gate task completion.
- refactorer: optimize quality while preserving behavior.

## 4. Required Events

1. task_created
2. task_planned
3. task_started
4. task_verifying
5. task_blocked
6. task_failed
7. task_quarantined
8. task_completed
9. task_reopened

