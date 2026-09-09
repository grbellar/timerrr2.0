"""Work accounting shared by the browser and authenticated agent API.

All timestamps are server UTC. Agent leases bound recorded execution; they do
not attest to CPU activity. Writes serialize on SQLite, including idempotency.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import text

from app.models import (
    Client,
    TimeEntry,
    WorkDraft,
    WorkEvent,
    WorkOperation,
    WorkSession,
    WorkSpan,
    db,
)

LEASE_SECONDS = 120


class WorkError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def iso(value):
    return value.isoformat() + "Z" if value else None


def parse_time(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(UTC).replace(tzinfo=None)
    except (ValueError, TypeError, AttributeError):
        raise WorkError("Use an ISO timestamp with an explicit timezone.")


def string(data, key, limit=100, required=True):
    value = data.get(key, "")
    if (
        not isinstance(value, str)
        or len(value) > limit
        or (required and not value.strip())
    ):
        raise WorkError(
            f"{key} must be {'a nonempty' if required else 'a'} string of at most {limit} characters."
        )
    return value.strip()


def integer(data, key, minimum=1, maximum=2147483647):
    value = data.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise WorkError(f"{key} must be an integer between {minimum} and {maximum}.")
    return value


def owned_work(user_id, work_id):
    work = WorkSession.query.filter_by(id=work_id, user_id=user_id).first()
    if not work:
        raise WorkError("Work session not found.", 404)
    return work


def event(work, at, kind, source, data=None, actor_id=None):
    db.session.add(
        WorkEvent(
            work=work,
            at=at,
            kind=kind,
            source=source,
            data=data or {},
            actor_id=actor_id,
        )
    )


def deadline(work):
    return work.started_at + timedelta(seconds=work.budget_seconds)


def span_end(span, at):
    candidates = [span.ended_at or at, span.work.finished_at or at]
    if span.actor_kind == "agent":
        candidates += [span.lease_until, deadline(span.work)]
    return max(span.started_at, min(candidates))


def union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def seconds(intervals):
    return round(sum((end - start).total_seconds() for start, end in intervals), 3)


def receipt(work, at=None, include_events=True):
    at = at or now()
    spans = []
    human, agents, waiting = [], [], []
    for span in sorted(work.spans, key=lambda s: (s.started_at, s.id or 0)):
        end = span_end(span, at)
        interval = (span.started_at, end)
        {"human": human, "agent": agents, "waiting": waiting}[span.actor_kind].append(
            interval
        )
        expired = (
            span.actor_kind == "agent"
            and min(span.lease_until, deadline(work)) <= at
            and not span.ended_at
        )
        reason = span.stop_reason
        if expired:
            reason = (
                "budget_exhausted"
                if deadline(work) <= span.lease_until
                else "lease_expired"
            )
        spans.append(
            {
                "id": span.id,
                "actor_id": span.actor_id,
                "actor_kind": span.actor_kind,
                "started_at": iso(span.started_at),
                "ended_at": iso(end)
                if span.ended_at or expired or work.finished_at
                else None,
                "seconds": seconds([interval]),
                "lease_until": iso(span.lease_until),
                "stop_reason": reason,
            }
        )
    client = db.session.get(Client, work.client_id)
    warnings = []
    if any(s["stop_reason"] == "lease_expired" for s in spans):
        warnings.append(
            "An agent disconnected. Execution is capped at its last lease; review the uncertain interval."
        )
    if not human:
        warnings.append(
            "No human effort recorded. Artifacts and agent execution do not establish human work time."
        )
    return {
        "id": work.id,
        "client_id": work.client_id,
        "client_name": client.name if client else "Deleted client",
        "title": work.title,
        "started_at": iso(work.started_at),
        "finished_at": iso(work.finished_at),
        "approved_at": iso(work.approved_at),
        "budget_seconds": work.budget_seconds,
        "budget_remaining_seconds": max(
            0, round((deadline(work) - (work.finished_at or at)).total_seconds(), 3)
        ),
        "budget_deadline": iso(deadline(work)),
        "server_time": iso(at),
        "elapsed_seconds": seconds([(work.started_at, work.finished_at or at)]),
        "human_seconds": seconds(union(human)),
        "agent_seconds": seconds(agents),
        "agent_elapsed_seconds": seconds(union(agents)),
        "waiting_seconds": seconds(union(waiting)),
        "human_intervals": [
            {"start_time": iso(s), "end_time": iso(e)} for s, e in union(human)
        ],
        "spans": spans,
        "warnings": warnings,
        "events": [
            {
                "id": e.id,
                "at": iso(e.at),
                "kind": e.kind,
                "actor_id": e.actor_id,
                "source": e.source,
                "data": e.data,
            }
            for e in (
                sorted(work.events, key=lambda e: (e.at, e.id or 0))
                if include_events
                else []
            )
        ],
    }


def expire_spans(work, at):
    for span in work.spans:
        if (
            span.actor_kind == "agent"
            and span.ended_at is None
            and span_end(span, at) <= at
        ):
            cutoff = min(span.lease_until, deadline(work))
            if cutoff <= at:
                span.ended_at = cutoff
                span.stop_reason = (
                    "budget_exhausted"
                    if deadline(work) <= span.lease_until
                    else "lease_expired"
                )
                event(work, cutoff, span.stop_reason, "server", actor_id=span.actor_id)


def start_actor(work, data, at, source):
    actor_id = string(data, "actor_id")
    kind = string(data, "actor_kind", 10)
    if kind not in ("human", "agent", "waiting"):
        raise WorkError("actor_kind must be human, agent, or waiting.")
    if any(s.actor_id == actor_id and s.ended_at is None for s in work.spans):
        raise WorkError(
            "Actor already active. Stop it before changing its activity.", 409
        )
    if any(s.actor_id == actor_id and s.actor_kind != kind for s in work.spans):
        raise WorkError("Use a distinct actor_id for each activity kind.")
    if kind == "agent" and at >= deadline(work):
        raise WorkError("Agent time budget exhausted.", 409)
    span = WorkSpan(
        work=work,
        actor_id=actor_id,
        actor_kind=kind,
        started_at=at,
        lease_until=min(at + timedelta(seconds=LEASE_SECONDS), deadline(work))
        if kind == "agent"
        else None,
    )
    db.session.add(span)
    event(work, at, "actor_started", source, {"actor_kind": kind}, actor_id)


def execute(user_id, action, data, source):
    """Run a mutation atomically and replay its exact first response on retries."""
    key = string(data, "request_id")
    fingerprint = hashlib.sha256(
        json.dumps([action, data, source], sort_keys=True).encode()
    ).hexdigest()
    try:
        db.session.execute(text("BEGIN IMMEDIATE"))
        previous = WorkOperation.query.filter_by(
            user_id=user_id, request_id=key
        ).first()
        if previous:
            if previous.fingerprint != fingerprint:
                raise WorkError(
                    "request_id was already used for different arguments.", 409
                )
            result = previous.response
            db.session.rollback()
            return result
        result = mutate(user_id, action, data, source)
        db.session.add(
            WorkOperation(
                user_id=user_id,
                request_id=key,
                fingerprint=fingerprint,
                response=result,
            )
        )
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def mutate(user_id, action, data, source):
    at = now()
    if action == "start_work":
        client_id = integer(data, "client_id")
        if not Client.query.filter_by(id=client_id, user_id=user_id).first():
            raise WorkError("Client not found.", 404)
        work = WorkSession(
            user_id=user_id,
            client_id=client_id,
            title=string(data, "title", 300),
            started_at=at,
            budget_seconds=integer(data, "budget_seconds", 1, 86400),
        )
        db.session.add(work)
        event(work, at, "work_started", source, {"budget_seconds": work.budget_seconds})
        start_actor(work, data, at, source)
    elif action in ("record_work_event", "finish_work"):
        work = owned_work(user_id, integer(data, "work_id"))
        if work.finished_at:
            raise WorkError("Work session is already finished.", 409)
        expire_spans(work, at)
        if action == "finish_work":
            for span in work.spans:
                if span.ended_at is None:
                    span.ended_at = at
                    span.stop_reason = "finished"
            work.finished_at = at
            event(
                work,
                at,
                "work_finished",
                source,
                {"summary": string(data, "summary", 4000, False)},
            )
        else:
            kind = string(data, "kind", 30)
            if kind == "actor_started":
                start_actor(work, data, at, source)
            elif kind in ("heartbeat", "actor_stopped"):
                actor_id = string(data, "actor_id")
                span = next(
                    (
                        s
                        for s in work.spans
                        if s.actor_id == actor_id and s.ended_at is None
                    ),
                    None,
                )
                if not span:
                    # Return the capped receipt so a runner can stop immediately.
                    if kind == "heartbeat":
                        db.session.flush()
                        return {
                            "work": receipt(work, at, include_events=False),
                            "continue_work": False,
                        }
                    raise WorkError("Actor is not active.", 409)
                if kind == "heartbeat":
                    if span.actor_kind != "agent":
                        raise WorkError("Only agent execution uses heartbeats.")
                    span.lease_until = min(
                        at + timedelta(seconds=LEASE_SECONDS), deadline(work)
                    )
                else:
                    span.ended_at = at
                    span.stop_reason = "stopped"
                event(work, at, kind, source, actor_id=actor_id)
            elif kind in ("note", "artifact"):
                content = {"text": string(data, "text", 4000)}
                if kind == "artifact":
                    url = string(data, "url", 2000)
                    parsed = urlsplit(url)
                    if (
                        parsed.scheme not in ("http", "https")
                        or not parsed.netloc
                        or parsed.username
                        or parsed.password
                    ):
                        raise WorkError(
                            "Artifact URL must be an HTTP(S) URL without credentials."
                        )
                    content["url"] = url
                event(work, at, kind, source, content)
            else:
                raise WorkError("Unknown event kind.")
    elif action == "draft_timesheet":
        return make_draft(user_id, data, at)
    elif action == "approve_draft":
        if source != "browser":
            raise WorkError("Approve drafts in the Timerrr website.", 403)
        return approve_draft(user_id, data, at)
    else:
        raise WorkError("Unknown action.", 404)
    db.session.flush()
    return {
        "work": receipt(work, at, include_events=data.get("kind") != "heartbeat"),
        "continue_work": not work.finished_at and at < deadline(work),
    }


def make_draft(user_id, data, at):
    start, end = parse_time(data.get("start_time")), parse_time(data.get("end_time"))
    if end <= start or end - start > timedelta(days=93):
        raise WorkError("Choose a positive date range of at most 93 days.")
    sessions = (
        WorkSession.query.filter(
            WorkSession.user_id == user_id,
            WorkSession.finished_at.is_not(None),
            WorkSession.approved_at.is_(None),
            WorkSession.started_at >= start,
            WorkSession.finished_at <= end,
        )
        .order_by(WorkSession.started_at)
        .all()
    )
    rows, receipts = [], []
    for work in sessions:
        r = receipt(work, at)
        receipts.append(r)
        for interval in r["human_intervals"]:
            rows.append(
                {
                    "row_id": len(rows),
                    "work_id": work.id,
                    "client_id": work.client_id,
                    "notes": work.title,
                    **interval,
                }
            )
    draft = WorkDraft(
        user_id=user_id,
        created_at=at,
        data={
            "start_time": iso(start),
            "end_time": iso(end),
            "rows": rows,
            "receipts": receipts,
            "limitations": [
                "Only finished, unapproved sessions fully contained in this range are included.",
                "Human intervals are proposed from recorded activity; agent minutes are excluded.",
                "Linked artifacts provide context, not inferred hours. Review gaps and overlapping existing entries.",
            ],
        },
    )
    db.session.add(draft)
    db.session.flush()
    return {"draft": serialize_draft(draft)}


def serialize_draft(draft):
    return {
        "id": draft.id,
        "created_at": iso(draft.created_at),
        "approved_at": iso(draft.approved_at),
        **draft.data,
        "approval": draft.approval,
    }


def approve_draft(user_id, data, at):
    draft = WorkDraft.query.filter_by(
        id=integer(data, "draft_id"), user_id=user_id
    ).first()
    if not draft:
        raise WorkError("Draft not found.", 404)
    if draft.approved_at:
        raise WorkError("Draft already approved.", 409)
    review = data.get("rows")
    if not isinstance(review, list) or len(review) > 1000:
        raise WorkError("rows must be a list of up to 1000 reviewed intervals.")
    source_rows = {row["row_id"]: row for row in draft.data["rows"]}
    works = {r["id"]: owned_work(user_id, r["id"]) for r in draft.data["receipts"]}
    if any(w.approved_at for w in works.values()):
        raise WorkError(
            "A session in this draft has already been reviewed in another draft.", 409
        )
    accepted, intervals, seen = [], [], set()
    for row in review:
        if not isinstance(row, dict):
            raise WorkError("Each row must be an object.")
        row_id = integer(row, "row_id", 0)
        if row_id not in source_rows or row_id in seen:
            raise WorkError("Unknown or duplicate draft row.")
        seen.add(row_id)
        original = source_rows[row_id]
        start, end = parse_time(row.get("start_time")), parse_time(row.get("end_time"))
        work = works[original["work_id"]]
        if not work.started_at <= start < end <= work.finished_at:
            raise WorkError("Reviewed intervals must stay within their work session.")
        if not Client.query.filter_by(id=work.client_id, user_id=user_id).first():
            raise WorkError("The client for this session no longer exists.", 409)
        if any(start < e and end > s for s, e in intervals):
            raise WorkError(
                "Reviewed human intervals overlap. Adjust or exclude duplicate rows.",
                409,
            )
        overlap = TimeEntry.query.filter(
            TimeEntry.user_id == user_id,
            TimeEntry.start_time < end,
            db.or_(TimeEntry.end_time.is_(None), TimeEntry.end_time > start),
        ).first()
        if overlap:
            raise WorkError(
                f"This interval overlaps existing time entry {overlap.id}. Adjust or exclude it.",
                409,
            )
        intervals.append((start, end))
        notes = string(row, "notes", 4000, False)
        entry = TimeEntry(
            user_id=user_id,
            client_id=work.client_id,
            start_time=start,
            end_time=end,
            notes=notes + f"\nWork receipt #{work.id}",
        )
        db.session.add(entry)
        db.session.flush()
        accepted.append(
            {
                "row_id": row_id,
                "entry_id": entry.id,
                "start_time": iso(start),
                "end_time": iso(end),
                "notes": notes,
            }
        )
    draft.approved_at = at
    draft.approval = {
        "rows": accepted,
        "excluded_row_ids": sorted(set(source_rows) - seen),
    }
    for work in works.values():
        work.approved_at = at
        event(
            work,
            at,
            "human_review",
            "browser",
            {"draft_id": draft.id, "approval": draft.approval},
        )
    db.session.flush()
    return {"draft": serialize_draft(draft)}
