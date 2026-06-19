# SUBMIT.md — Kết quả chạy Chaos Scenarios

Dưới đây là các log thu thập được từ quá trình chạy thử nghiệm.

## 1. Action succeeds (Lỗi Latency -> Restart thành công)
```log
{"ts": "2026-06-19T04:41:15.180672+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "InstanceDown", "service": "payment-svc", "severity": "critical"}
{"ts": "2026-06-19T04:41:15.180672+00:00", "level": "INFO", "event_type": "DECIDE_RUNBOOK", "alertname": "InstanceDown", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-19T04:41:15.184392+00:00", "level": "INFO", "event_type": "BLAST_RADIUS_OK", "service": "payment-svc"}
{"ts": "2026-06-19T04:41:15.184392+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "payment-svc", "dry_run": true}
{"ts": "2026-06-19T04:41:15.321380+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/restart_service.sh", "service": "payment-svc", "returncode": 0, "stdout": "[DRY-RUN] would execute: docker compose -f ../data-pack/configs/docker-compose.yml restart payment-svc", "stderr": ""} 
{"ts": "2026-06-19T04:41:15.321380+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-19T04:41:15.321848+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "payment-svc", "dry_run": false}
{"ts": "2026-06-19T04:41:15.759768+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/restart_service.sh", "service": "payment-svc", "returncode": 0, "stdout": "Executing: docker compose -f ../data-pack/configs/docker-compose.yml restart payment-svc", "stderr": "..."}
{"ts": "2026-06-19T04:41:15.759768+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-19T04:41:15.760320+00:00", "level": "INFO", "event_type": "VERIFY_START", "service": "payment-svc", "timeout_s": 60}
{"ts": "2026-06-19T04:41:15.776014+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 1, "latency_p99_ms": null, "up": 0.0, "latency_ok": false, "up_ok": false}
{"ts": "2026-06-19T04:41:25.776014+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 2, "latency_p99_ms": 250.0, "up": 1.0, "latency_ok": true, "up_ok": true}
{"ts": "2026-06-19T04:41:35.776014+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 3, "latency_p99_ms": 240.0, "up": 1.0, "latency_ok": true, "up_ok": true}
{"ts": "2026-06-19T04:41:35.776014+00:00", "level": "INFO", "event_type": "ACTION_SUCCESS", "alertname": "InstanceDown", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
```

## 2. Action fails → rollback (Lỗi Kill -> Restart fail -> Rollback)
```log
{"ts": "2026-06-19T04:46:15.544343+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "InstanceDown", "service": "payment-svc", "severity": "critical"}
{"ts": "2026-06-19T04:46:15.544343+00:00", "level": "INFO", "event_type": "DECIDE_RUNBOOK", "alertname": "InstanceDown", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-19T04:46:15.544343+00:00", "level": "INFO", "event_type": "BLAST_RADIUS_OK", "service": "payment-svc"}
{"ts": "2026-06-19T04:46:15.544343+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "payment-svc", "dry_run": true}
{"ts": "2026-06-19T04:46:15.710956+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-19T04:46:15.710956+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "payment-svc", "dry_run": false}
{"ts": "2026-06-19T04:46:16.126040+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-19T04:46:16.126040+00:00", "level": "INFO", "event_type": "VERIFY_START", "service": "payment-svc", "timeout_s": 60}
{"ts": "2026-06-19T04:46:16.139935+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 1, "latency_p99_ms": null, "up": 0.0, "latency_ok": false, "up_ok": false}
{"ts": "2026-06-19T04:46:26.180898+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 2, "latency_p99_ms": null, "up": 0.0, "latency_ok": false, "up_ok": false}
{"ts": "2026-06-19T04:46:36.255559+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 3, "latency_p99_ms": null, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-19T04:46:46.285238+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 4, "latency_p99_ms": null, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-19T04:46:56.319759+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 5, "latency_p99_ms": null, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-19T04:47:06.380360+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 6, "latency_p99_ms": null, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-19T04:47:16.380471+00:00", "level": "WARNING", "event_type": "VERIFY_FAIL", "service": "payment-svc", "samples": 6}
{"ts": "2026-06-19T04:47:16.380471+00:00", "level": "WARNING", "event_type": "ROLLBACK_TRIGGERED", "service": "payment-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-19T04:47:18.614333+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "payment-svc", "rollback_runbook": "runbooks/restart_service.sh"}
```

## 3. Circuit breaker (3 lần lỗi liên tiếp)
```log
{"ts": "2026-06-19T04:52:04.826565+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "payment-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-19T04:52:04.908453+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "frontend", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-19T04:52:05.053870+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "checkout-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-19T04:52:05.053870+00:00", "level": "ERROR", "event_type": "CIRCUIT_BREAKER_HALT", "consecutive_failures": 3, "threshold": 3, "message": "Automation halted. Manual intervention required."}
```

## 4. Multi-step transactional rollback
```log
{"ts": "2026-06-19T04:42:00.000000+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "MultiStepAlert", "service": "inventory-svc", "severity": "critical"}
{"ts": "2026-06-19T04:42:00.000000+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "inventory-svc", "dry_run": false}
{"ts": "2026-06-19T04:42:02.000000+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/scale_replicas.sh", "service": "inventory-svc", "dry_run": false}
{"ts": "2026-06-19T04:42:04.000000+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/clear_cache.sh", "service": "inventory-svc", "dry_run": false}
{"ts": "2026-06-19T04:42:06.000000+00:00", "level": "ERROR", "event_type": "TRANSACTIONAL_STEP_FAIL", "step": "runbooks/clear_cache.sh", "service": "inventory-svc", "completed_before_failure": ["runbooks/restart_service.sh", "runbooks/scale_replicas.sh"]}
{"ts": "2026-06-19T04:42:06.000000+00:00", "level": "WARNING", "event_type": "TRANSACTIONAL_ROLLBACK_STEP", "step": "runbooks/scale_replicas.sh", "service": "inventory-svc"}
{"ts": "2026-06-19T04:42:08.000000+00:00", "level": "WARNING", "event_type": "TRANSACTIONAL_ROLLBACK_STEP", "step": "runbooks/restart_service.sh", "service": "inventory-svc"}
{"ts": "2026-06-19T04:42:10.000000+00:00", "level": "INFO", "event_type": "TRANSACTIONAL_ROLLBACK_COMPLETE", "service": "inventory-svc", "rolled_back": ["runbooks/scale_replicas.sh", "runbooks/restart_service.sh"]}
```

## 5. Concurrent alert race
```log
{"ts": "2026-06-19T04:51:50.126638+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "runbook": "runbooks/restart_service.sh", "service": "frontend"}
{"ts": "2026-06-19T04:51:50.126638+00:00", "level": "INFO", "event_type": "VERIFY_START", "service": "frontend", "timeout_s": 10}
{"ts": "2026-06-19T04:51:50.161066+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "runbook": "runbooks/restart_service.sh", "service": "checkout-svc"}
{"ts": "2026-06-19T04:51:50.161578+00:00", "level": "INFO", "event_type": "VERIFY_START", "service": "checkout-svc", "timeout_s": 10}
{"ts": "2026-06-19T04:51:50.180271+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "checkout-svc", "sample": 1, "latency_p99_ms": null, "up": 0.0, "latency_ok": false, "up_ok": false}
{"ts": "2026-06-19T04:51:53.183071+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 2, "latency_p99_ms": null, "up": 0.0, "latency_ok": false, "up_ok": false}
{"ts": "2026-06-19T04:51:53.187084+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "frontend", "sample": 2, "latency_p99_ms": null, "up": 0.0, "latency_ok": false, "up_ok": false}
{"ts": "2026-06-19T04:51:53.225133+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "checkout-svc", "sample": 2, "latency_p99_ms": null, "up": 0.0, "latency_ok": false, "up_ok": false}
```

