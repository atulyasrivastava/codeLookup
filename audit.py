import json
import time
from datetime import datetime, timezone

AUDIT_LOG_FILE = "audit_log.jsonl"

def log_query(query, results, latency_ms, model_used="nomic-embed-text"):
    """Append one structured audit record per query, JSON lines format."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "model_used": model_used,
        "latency_ms": round(latency_ms, 2),
        "results": [
            {"name": r.payload["name"], "file": r.payload["file"], "score": round(r.score, 3)}
            for r in results
        ]
    }
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")