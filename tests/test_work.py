import hashlib
import json
import os
import re
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app import work_service as service
from app.models import AgentToken, Client, TimeEntry, User, WorkSession, db


class WorkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {"DATABASE_PATH": cls.directory.name + "/test.db"}):
            cls.app, _ = create_app()
        cls.app.config.update(TESTING=True, SECRET_KEY="test-only")

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.user = User(email="test@example.com", password_hash="unused")
        self.user.start_trial()
        other = User(email="other@example.com", password_hash="unused")
        other.start_trial()
        db.session.add_all([self.user, other])
        db.session.flush()
        self.client_record = Client(user_id=self.user.id, name="Acme", hourly_rate=100)
        self.other_client = Client(user_id=other.id, name="Other")
        db.session.add_all([self.client_record, self.other_client])
        for raw, owner, scopes in [
            ("full", self.user, "work:read work:write draft:write"),
            ("read", self.user, "work:read"),
            ("other", other, "work:read work:write draft:write"),
        ]:
            db.session.add(
                AgentToken(
                    user_id=owner.id,
                    name=raw,
                    token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                    scopes=scopes,
                    expires_at=service.now() + timedelta(days=1),
                )
            )
        db.session.commit()
        self.http = self.app.test_client()
        self.t = service.now().replace(microsecond=0)

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def call(self, action, data=None, token="full", at=None, status=200):
        with patch("app.work_service.now", return_value=at or self.t):
            r = self.http.post(
                "/api/agent/" + action,
                json=data or {},
                headers={"Authorization": "Bearer " + token},
            )
        self.assertEqual(r.status_code, status, r.get_json())
        return r.get_json()

    def mutate(self, action, data, **kw):
        return self.call(action, {"request_id": str(uuid4()), **data}, **kw)

    def start(self, actor_kind="human", **kw):
        return self.mutate(
            "start_work",
            {
                "client_id": self.client_record.id,
                "title": "Checkout fix",
                "budget_seconds": 1200,
                "actor_id": "me",
                "actor_kind": actor_kind,
            },
            **kw,
        )["work"]["id"]

    def finish(self, work_id, seconds=60):
        return self.mutate(
            "finish_work",
            {"work_id": work_id, "summary": "Done"},
            at=self.t + timedelta(seconds=seconds),
        )

    def draft(self):
        return self.mutate(
            "draft_timesheet",
            {
                "start_time": service.iso(self.t - timedelta(seconds=1)),
                "end_time": service.iso(self.t + timedelta(days=1)),
            },
        )["draft"]

    def browser(self):
        with self.http.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
            session["_fresh"] = True
            session["work_csrf"] = "test-csrf"

    def approve(self, draft, rows=None, status=200):
        self.browser()
        r = self.http.post(
            "/api/agent/approve_draft",
            json={
                "request_id": str(uuid4()),
                "draft_id": draft["id"],
                "rows": draft["rows"] if rows is None else rows,
            },
            headers={"X-CSRF-Token": "test-csrf"},
        )
        self.assertEqual(r.status_code, status, r.get_json())
        return r.get_json()

    def test_replay_and_key_conflict(self):
        data = {
            "request_id": "same",
            "client_id": self.client_record.id,
            "title": "Fix",
            "budget_seconds": 20,
            "actor_id": "a",
            "actor_kind": "agent",
        }
        first = self.call("start_work", data)
        second = self.call("start_work", data, at=self.t + timedelta(seconds=1))
        self.assertEqual(first, second)
        self.assertEqual(WorkSession.query.count(), 1)
        self.call("start_work", {**data, "title": "Different"}, status=409)

    def test_concurrent_retries_create_one_session(self):
        from concurrent.futures import ThreadPoolExecutor

        data = {
            "request_id": "concurrent",
            "client_id": self.client_record.id,
            "title": "Concurrent",
            "budget_seconds": 60,
            "actor_id": "agent",
            "actor_kind": "agent",
        }

        def send():
            with self.app.test_client() as client:
                response = client.post(
                    "/api/agent/start_work",
                    json=data,
                    headers={"Authorization": "Bearer full"},
                )
                return response.status_code, response.get_json()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: send(), range(4)))
        self.assertTrue(all(status == 200 for status, _ in results), results)
        self.assertTrue(all(body == results[0][1] for _, body in results))
        self.assertEqual(WorkSession.query.count(), 1)

    def test_cross_account_scopes_and_auth(self):
        wid = self.start()
        self.call("get_work", {"work_id": wid}, token="other", status=404)
        self.call("get_active_work", token="invalid", status=401)
        self.mutate("finish_work", {"work_id": wid}, token="read", status=403)
        self.mutate(
            "start_work",
            {
                "client_id": self.other_client.id,
                "title": "No",
                "budget_seconds": 20,
                "actor_id": "a",
                "actor_kind": "agent",
            },
            status=404,
        )
        token = AgentToken.query.filter_by(name="full").first()
        token.revoked_at = self.t
        db.session.commit()
        self.call("get_work", {"work_id": wid}, status=401)

    def test_parallel_agents_and_human_union(self):
        wid = self.start()
        for actor, kind in [
            ("agent1", "agent"),
            ("agent2", "agent"),
            ("reviewer", "human"),
        ]:
            self.mutate(
                "record_work_event",
                {
                    "work_id": wid,
                    "kind": "actor_started",
                    "actor_id": actor,
                    "actor_kind": kind,
                },
            )
        r = self.finish(wid)["work"]
        self.assertEqual(r["human_seconds"], 60)
        self.assertEqual(r["agent_seconds"], 120)
        self.assertEqual(r["elapsed_seconds"], 60)
        self.assertEqual(r["agent_elapsed_seconds"], 60)

    def test_lease_expiry_and_no_resurrection(self):
        wid = self.start("agent")
        r = self.call("get_work", {"work_id": wid}, at=self.t + timedelta(seconds=300))[
            "work"
        ]
        self.assertEqual(r["agent_seconds"], 120)
        self.assertTrue(r["warnings"])
        r = self.mutate(
            "record_work_event",
            {"work_id": wid, "kind": "heartbeat", "actor_id": "me"},
            at=self.t + timedelta(seconds=300),
        )
        self.assertFalse(r["continue_work"])
        self.assertEqual(r["work"]["spans"][0]["stop_reason"], "lease_expired")

    def test_budget_and_heartbeat_renewal(self):
        data = {
            "client_id": self.client_record.id,
            "title": "Fix",
            "budget_seconds": 150,
            "actor_id": "a",
            "actor_kind": "agent",
        }
        wid = self.mutate("start_work", data)["work"]["id"]
        self.mutate(
            "record_work_event",
            {"work_id": wid, "kind": "heartbeat", "actor_id": "a"},
            at=self.t + timedelta(seconds=90),
        )
        r = self.call("get_work", {"work_id": wid}, at=self.t + timedelta(seconds=200))[
            "work"
        ]
        self.assertEqual(r["agent_seconds"], 150)
        self.assertEqual(r["budget_remaining_seconds"], 0)
        self.assertEqual(r["spans"][0]["stop_reason"], "budget_exhausted")

    def test_review_and_duplicate_drafts(self):
        wid = self.start()
        self.finish(wid)
        draft = self.draft()
        second = self.draft()
        self.assertEqual(TimeEntry.query.count(), 0)
        self.mutate(
            "approve_draft",
            {"draft_id": draft["id"], "rows": draft["rows"]},
            status=403,
        )
        self.approve(draft)
        self.assertEqual(TimeEntry.query.count(), 1)
        self.assertEqual(TimeEntry.query.first().duration, 60)
        self.approve(second, status=409)
        self.assertEqual(TimeEntry.query.count(), 1)

    def test_overlap_rejected_without_partial_writes(self):
        a = self.start()
        b = self.start()
        self.finish(a)
        self.finish(b)
        draft = self.draft()
        self.approve(draft, status=409)
        self.assertEqual(TimeEntry.query.count(), 0)
        self.approve(draft, rows=draft["rows"][:1])
        self.assertEqual(TimeEntry.query.count(), 1)

    def test_existing_timer_overlap_rejected(self):
        wid = self.start()
        self.finish(wid)
        db.session.add(
            TimeEntry(
                user_id=self.user.id,
                client_id=self.client_record.id,
                start_time=self.t,
                end_time=None,
            )
        )
        db.session.commit()
        self.approve(self.draft(), status=409)

    def test_agent_only_draft_does_not_invent_human_time(self):
        wid = self.start("agent")
        self.finish(wid)
        d = self.draft()
        self.assertEqual(d["rows"], [])
        self.assertIn("No human effort", d["receipts"][0]["warnings"][0])
        self.approve(d)
        self.assertEqual(TimeEntry.query.count(), 0)

    def test_invalid_values_and_artifact_schemes(self):
        wid = self.start()
        self.mutate(
            "record_work_event",
            {
                "work_id": wid,
                "kind": "artifact",
                "text": "x",
                "url": "javascript:alert(1)",
            },
            status=400,
        )
        self.mutate(
            "record_work_event",
            {"work_id": wid, "kind": "note", "text": {"bad": "value"}},
            status=400,
        )
        self.mutate(
            "draft_timesheet",
            {"start_time": "2026-01-01", "end_time": "2026-01-03"},
            status=400,
        )
        self.call("get_work", {"work_id": True}, status=400)

    def test_csrf_and_browser_pages(self):
        self.browser()
        r = self.http.post("/api/agent/list_work", json={})
        self.assertEqual(r.status_code, 403)
        for path in ["/work", "/timer", "/entries", "/timesheets", "/settings"]:
            self.assertEqual(self.http.get(path).status_code, 200, path)
        r = self.http.post(
            "/api/agent-tokens",
            json={"name": "new", "scopes": ["work:read"]},
            headers={"X-CSRF-Token": "test-csrf"},
        )
        self.assertEqual(r.status_code, 201)
        self.assertNotIn(
            r.json["token"], self.http.get("/api/agent-tokens").get_data(as_text=True)
        )

    def test_expired_subscription_rejected(self):
        self.user.trial_ends_at = self.t - timedelta(days=1)
        db.session.commit()
        self.call("get_active_work", status=403)
        self.browser()
        self.assertEqual(self.http.get("/work").status_code, 200)
        token = AgentToken.query.filter_by(name="full").first()
        response = self.http.delete(
            f"/api/agent-tokens/{token.id}", headers={"X-CSRF-Token": "test-csrf"}
        )
        self.assertEqual(response.status_code, 200)

    def test_public_pages_and_metadata(self):
        for path in [
            "/",
            "/guides/mcp",
            "/guides/parallel-time",
            "/guides/agent-timekeeping",
        ]:
            r = self.http.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertIn(b'rel="canonical"', r.data)
            self.assertIn(b"application/ld+json", r.data)
            schema = re.search(
                r'<script type="application/ld\+json">(.*?)</script>',
                r.get_data(as_text=True),
                re.DOTALL,
            )
            self.assertEqual(
                json.loads(schema.group(1))["@context"], "https://schema.org"
            )


if __name__ == "__main__":
    unittest.main()
