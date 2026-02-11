# Telemetry Metrics v2

Status: Active  
Last Updated: 2026-02-11

## 1. Objective

Track quality, security, and delivery health for autonomous orchestration.

## 2. Core Delivery Metrics

1. Round trips per task  
Target: <= 3

2. Diff size per file  
Target: <= 100 LOC

3. Test failure rate  
Target: <= 10%

4. Lead time from ready -> completed  
Target: team-defined by work type

## 3. Security Metrics

1. Policy gate pass rate  
Target: 100%

2. Secret leak incidents  
Target: 0

3. Quarantine trigger count  
Target: near 0, investigated on every occurrence

4. Mean time to contain (MTTC) incident  
Target: < 30 minutes

5. Mean time to recover (MTTR) incident  
Target: < 4 hours

## 4. Domain Integrity Metrics

1. ID integrity pass rate  
Target: 100%

2. Coordinate accuracy  
Target: average error <= 2px

3. Match quality baseline compliance  
Target: agreed baseline maintained

## 5. Required Event Payload

Each orchestrated task event should include:

1. task_id
2. risk_class
3. actor_role
4. state_from
5. state_to
6. touched_files_count
7. tests_passed_count
8. tests_failed_count
9. security_check_status
10. approval_count
11. incident_flag
12. timestamp

## 6. Reporting Cadence

1. Daily: delivery + security snapshot
2. Weekly: trend and anomaly review
3. Monthly: game-day drill outcome and control updates

