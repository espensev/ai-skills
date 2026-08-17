## Output Contracts

Every command supports `--format json` for machine-readable output. When
`--format json` is passed, the command outputs **only** a single JSON object
to stdout — no preamble, no markdown, no commentary.

### Note Output

```json
{
  "action": "note",
  "recorded": true,
  "observation": {
    "ts": "2026-03-21T14:30:00Z",
    "cat": "risk",
    "summary": "no tests for payment module",
    "severity": "warning",
    "status": "open",
    "confidence": 0.5
  }
}
```

If deduplicated (skipped):
```json
{
  "action": "note",
  "recorded": false,
  "reason": "duplicate",
  "existing": {"cat": "risk", "summary": "no tests for payment module"}
}
```

### List Output

```json
{
  "action": "list",
  "count": 3,
  "filters": {"category": "risk", "status": "open"},
  "observations": [
    {"ts": "2026-03-21T09:15:00Z", "cat": "risk", "summary": "no tests for payment module", "severity": "warning", "status": "open", "confidence": 0.8, "files": ["src/payment.py"]},
    {"ts": "2026-03-21T14:30:00Z", "cat": "risk", "summary": "API keys in env without rotation", "severity": "critical", "status": "open", "confidence": 0.9, "files": []}
  ]
}
```

### Status Output

```json
{
  "action": "status",
  "total": 23,
  "by_status": {"open": 18, "resolved": 3, "stale": 2},
  "by_severity": {"info": 18, "warning": 4, "critical": 1},
  "by_category": {
    "decision": {"open": 3, "resolved": 1, "stale": 1},
    "risk": {"open": 3, "resolved": 1, "stale": 0}
  },
  "last_observation": "2026-03-21T14:30:00Z",
  "last_synthesis": "2026-03-20T10:00:00Z",
  "metrics_tracked": 3
}
```

### Scan Output

```json
{
  "action": "scan",
  "probes_run": 5,
  "metrics_updated": [
    {"key": "dirty_file_count", "value": 5, "previous": 3, "delta": 2},
    {"key": "todo_count", "value": 42, "previous": 38, "delta": 4}
  ],
  "observations_emitted": [
    {"cat": "drift", "summary": "TODO count increased by 4 (now 42)", "severity": "warning", "recorded": true}
  ],
  "observations_resolved": [
    {"cat": "risk", "summary": "dirty file count above threshold", "reason": "metric recovered"}
  ]
}
```

### Briefing Output

```json
{
  "action": "briefing",
  "status": "warning",
  "health": "degraded",
  "summary": "2 warnings, 0 critical — 15 open observations",
  "critical": [],
  "warnings": [
    {"cat": "risk", "summary": "no tests for payment module", "files": ["src/payment.py"]},
    {"cat": "drift", "summary": "auth module untouched for 3 weeks", "files": ["src/auth/"]}
  ],
  "metrics": {
    "dirty_file_count": 3,
    "todo_count": 42,
    "plans_executing": 1
  },
  "open_count": 15,
  "next_actions": [
    "Add test coverage for payment module",
    "Review auth module for staleness"
  ]
}
```

`health` values: `healthy` (0 critical, 0 warning), `degraded` (warnings only),
`unhealthy` (any critical).

### Check Output

```json
{
  "action": "check",
  "gate": "pass",
  "blockers": [],
  "warnings": ["no tests for payment module"],
  "open_critical": 0,
  "open_blockers": 0,
  "open_regressions": 0
}
```

Exit code: `0` if gate=pass, `1` if gate=fail.

### Cycle Output

```json
{
  "action": "cycle",
  "scan": {"probes_run": 5, "metrics_updated": 3, "observations_emitted": 1},
  "stale": {"marked": 2},
  "synthesize": {"file": "docs/observer/project-intelligence.md", "sections": 9},
  "status": {"total": 23, "open": 16, "critical": 0, "warning": 3}
}
```

### Resolve Output

```json
{
  "action": "resolve",
  "id": "2026-03-21T09:15:00Z:risk:no tests for payment module",
  "status": "resolved",
  "resolved_at": "2026-03-22T10:00:00Z",
  "resolved_detail": "Added pytest coverage in test_payment.py"
}
```

---
