# Orchestrator State Machine v2

Status: Active  
Last Updated: 2026-02-11

## 1. States

- pending
- ready
- in_progress
- verifying
- blocked
- failed
- quarantined
- completed

## 2. Valid Transitions

1. pending -> ready  
Condition: dependencies resolved and plan approved.

2. ready -> in_progress  
Condition: agent assigned and scope locked.

3. in_progress -> verifying  
Condition: implementation complete with evidence.

4. verifying -> completed  
Condition: all required checks and approvals pass.

5. in_progress -> blocked  
Condition: blocker discovered and documented.

6. in_progress -> failed  
Condition: non-transient failure.

7. verifying -> failed  
Condition: checks fail and require rework.

8. any_active_state -> quarantined  
Condition: security anomaly or policy violation detected.

9. blocked -> ready  
Condition: blocker resolved.

10. failed -> ready  
Condition: retry approved with remediation plan.

11. quarantined -> ready  
Condition: containment done and human approval granted.

## 3. Transition Guards

### Entering in_progress

1. Risk class is assigned.
2. Acceptance criteria exist.
3. Security controls exist for MEDIUM/HIGH.

### Entering verifying

1. Touched files are recorded.
2. Required tests are listed.
3. Domain checks are selected where required.

### Entering completed

1. Verifier status is PASS.
2. Required approvals are granted.
3. No open incident flag.

### Entering quarantined

1. Incident flag is true.
2. Containment task is created.
3. Write access to protected branch is blocked.

## 4. Invalid Transitions

1. completed -> any_other_state (immutable by default)
2. pending -> completed (verification bypass)
3. ready -> completed (execution bypass)
4. quarantined -> completed (containment bypass)

## 5. Audit Fields per Transition

1. actor
2. previous_state
3. new_state
4. reason
5. timestamp
6. related_task_or_incident_id

