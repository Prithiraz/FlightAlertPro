"""
Lightweight reliability metrics recording.

Metrics are written to the ``service_metrics`` Supabase table so they survive
restarts.  All writes are best-effort – a failure never propagates to the
caller.

Usage
-----
    from metrics import record_metric, record_request

    # raw metric
    record_metric("api_request_count", 1, {"endpoint": "search"})

    # convenience wrapper used by middleware
    await record_request(path="/api/search", status_code=200, duration_ms=142)
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Simple in-process counters used by the metrics middleware (reset on restart).
_counters: Dict[str, float] = {}


def _get_supabase():
    from supabase import create_client
    from config import config
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


def record_metric(
    metric_name: str,
    value: float,
    labels: Optional[Dict[str, Any]] = None,
) -> None:
    """Write a single metric row to ``service_metrics``.  Fire-and-forget."""
    try:
        supabase = _get_supabase()
        row: Dict[str, Any] = {"metric_name": metric_name, "value": value}
        if labels:
            row["labels_json"] = labels
        supabase.table("service_metrics").insert(row).execute()
    except Exception as exc:  # pragma: no cover
        logger.debug("metrics: failed to record %s: %s", metric_name, exc)


def record_request(
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Record per-request metrics (count, error count, latency)."""
    try:
        # Bucket the path to avoid high-cardinality keys
        endpoint_group = _endpoint_group(path)
        labels = {"endpoint": endpoint_group}

        record_metric("api_request_count", 1, labels)
        if status_code >= 500:
            record_metric("api_error_count", 1, labels)

        # Simple latency histogram bucket
        bucket = _latency_bucket(duration_ms)
        record_metric(
            "api_latency_ms",
            duration_ms,
            {"endpoint": endpoint_group, "bucket": bucket},
        )
    except Exception as exc:  # pragma: no cover
        logger.debug("metrics: record_request failed: %s", exc)


def record_notification(success: bool, channel: str = "unknown") -> None:
    """Record notification success/failure."""
    metric = "notification_success_count" if success else "notification_failure_count"
    record_metric(metric, 1, {"channel": channel})


def record_search_latency(provider: str, latency_ms: float, ok: bool) -> None:
    """Record a search provider call result."""
    metric = "provider_success" if ok else "provider_failure"
    record_metric(metric, 1, {"provider": provider})
    record_metric("search_latency_ms", latency_ms, {"provider": provider})


def record_worker_run() -> None:
    """Record the timestamp of the last worker run as epoch seconds."""
    import time as _t
    record_metric("worker_last_run_ts", _t.time())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _endpoint_group(path: str) -> str:
    """Collapse high-cardinality paths to a group name."""
    segments = [s for s in path.split("/") if s]
    if len(segments) >= 2:
        return "/" + "/".join(segments[:2])
    return path or "/"


def _latency_bucket(ms: float) -> str:
    if ms < 100:
        return "<100ms"
    if ms < 500:
        return "<500ms"
    if ms < 1000:
        return "<1s"
    if ms < 3000:
        return "<3s"
    return ">=3s"
