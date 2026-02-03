# Task State Model

**Purpose**: Define task lifecycle and state transitions

## Task States

```
pending → in_progress → completed
              ↓
            blocked → pending
              ↓
            failed → pending (retry)
```

### State Definitions

| State | Description | Next States |
|:---|:---|:---|
| **pending** | Task awaiting execution | in_progress |
| **in_progress** | Task currently being worked on | completed, blocked, failed |
| **blocked** | Task blocked by dependency or issue | pending (after resolution) |
| **failed** | Task failed with error | pending (retry) or abandoned |
| **completed** | Task successfully finished | - |

## Task Model

```python
@dataclass
class Task:
    task_id: str
    title: str
    description: str
    status: TaskStatus  # pending | in_progress | blocked | completed | failed
    assigned_to: AgentRole  # implementer | investigator | verifier | refactorer
    acceptance_criteria: List[str]
    dependencies: List[str]  # Task IDs
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
```

## Agent Roles

| Role | Responsibility |
|:---|:---|
| **implementer** | Code implementation |
| **investigator** | Root cause analysis |
| **verifier** | Testing and validation |
| **refactorer** | Code quality improvement |

## Event Types

- `task_created`
- `task_started`
- `task_blocked`
- `task_failed`
- `task_completed`
- `task_reassigned`

**Status**: Phase 0 定義完了、Phase 2以降で実装
