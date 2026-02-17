# State Machine

**Purpose**: Define state transitions and validation rules

## State Transition Rules

### Valid Transitions

```
pending → in_progress
  Condition: Task dependencies satisfied
  Action: Assign to agent, start work

in_progress → completed
  Condition: All acceptance criteria PASS
  Action: Mark complete, trigger next tasks

in_progress → blocked
  Condition: Dependency issue or blocker found
  Action: Pause work, create blocker task

in_progress → failed
  Condition: Unrecoverable error
  Action: Log error, decide retry or abandon

blocked → pending
  Condition: Blocker resolved
  Action: Reset to pending for reassignment

failed → pending
  Condition: Manual retry requested
  Action: Reset to pending, increment retry count
```

### Invalid Transitions

```
completed → * (任意の状態)
  Reason: Completed tasks are immutable

pending → completed (直接)
  Reason: Must go through in_progress

pending → blocked
  Reason: Can only be blocked while in_progress
```

## Validation Rules

### Task Start (pending → in_progress)

- ✅ All dependencies completed
- ✅ Agent assigned
- ✅ Acceptance criteria defined

### Task Complete (in_progress → completed)

- ✅ All acceptance criteria PASS
- ✅ Verifier approved
- ✅ No blocking issues

### Task Block (in_progress → blocked)

- ✅ Blocker reason documented
- ✅ Blocker task created
- ✅ Owner notified

## Metrics Tracking

For each state transition:
- Timestamp
- Duration in previous state
- Reason for transition
- User/agent who triggered

**Status**: Phase 0 定義完了、Phase 2以降で実装
