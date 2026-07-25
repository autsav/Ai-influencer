from datetime import datetime, timezone

from supabase import create_client

from aeloria.config import Settings, get_settings


class Db:
    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self._client = create_client(s.supabase_url, s.supabase_service_key)

    def insert(self, table: str, row: dict) -> dict:
        res = self._client.table(table).insert(row).execute()
        return res.data[0]

    def select(self, table: str, filters: dict | None = None, limit: int = 100) -> list[dict]:
        q = self._client.table(table).select("*")
        for k, v in (filters or {}).items():
            q = q.eq(k, v)
        return q.limit(limit).execute().data

    def _select_paged(self, build_query, page_size: int = 1000) -> list[dict]:
        """Exhaustively page a query (fresh query per page via `build_query`).
        Unlike select(), results don't silently stop at a row cap."""
        rows: list[dict] = []
        offset = 0
        while True:
            batch = build_query().range(offset, offset + page_size - 1).execute().data
            rows.extend(batch)
            if len(batch) < page_size:
                return rows
            offset += page_size

    def select_all(self, table: str, filters: dict | None = None,
                   order: str | None = None, page_size: int = 1000) -> list[dict]:
        def build():
            q = self._client.table(table).select("*")
            for k, v in (filters or {}).items():
                q = q.eq(k, v)
            return q.order(order) if order else q
        return self._select_paged(build, page_size=page_size)

    def select_posts_published_since(self, cutoff_iso: str) -> list[dict]:
        def build():
            return (
                self._client.table("posts").select("*")
                .gte("published_at", cutoff_iso).order("published_at")
            )
        return self._select_paged(build)

    def select_metrics_for_posts(self, post_ids: list[str]) -> list[dict]:
        if not post_ids:
            return []

        def build():
            return self._client.table("metrics").select("*").in_("post_id", list(post_ids))
        return self._select_paged(build)

    def latest_metric_for_post(self, post_id: str) -> dict | None:
        rows = (
            self._client.table("metrics").select("*")
            .eq("post_id", post_id).order("captured_at", desc=True)
            .limit(1).execute().data
        )
        return rows[0] if rows else None

    def sum_media_cost_today(self, engine: str) -> float:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
        q = self._client.table("media_assets").select("cost").eq("engine", engine)
        rows = q.gte("created_at", today).execute().data
        return float(sum(r["cost"] for r in rows))

    def update(self, table: str, row_id: str, fields: dict) -> dict:
        res = self._client.table(table).update(fields).eq("id", row_id).execute()
        return res.data[0] if res.data else {}

    def get_credential(self, platform: str) -> dict | None:
        rows = self.select("platform_credentials", {"platform": platform}, limit=1)
        return rows[0] if rows else None

    def upsert_credential(self, platform: str, access_token: str, expires_at) -> dict:
        existing = self.get_credential(platform)
        if existing:
            return self.update("platform_credentials", existing["id"], {
                "access_token": access_token,
                "expires_at": expires_at,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        return self.insert("platform_credentials", {
            "platform": platform,
            "access_token": access_token,
            "expires_at": expires_at,
        })

    def update_credential_token(self, platform: str, access_token: str, expires_at) -> dict:
        existing = self.get_credential(platform)
        if not existing:
            return {}
        return self.update("platform_credentials", existing["id"], {
            "access_token": access_token,
            "expires_at": expires_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def select_due_for_publish(self, platform: str) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        rows = (
            self._client.table("queue").select("*")
            .eq("approval", "approved")
            .lte("slot_time", now)
            .contains("platforms", [platform])
            .execute().data
        )
        if not rows:
            return []
        qids = [r["id"] for r in rows]
        posted = (
            self._client.table("posts").select("queue_id")
            .in_("queue_id", qids).execute().data
        )
        posted_ids = {p["queue_id"] for p in posted}
        return [r for r in rows if r["id"] not in posted_ids]

    def current_follower_count(self) -> int:
        # Latest daily follower snapshot (IG, instagram platform). 0 until S5 populates.
        rows = (
            self._client.table("follower_snapshots").select("followers")
            .eq("platform", "instagram")
            .order("captured_at", desc=True).limit(1).execute().data
        )
        return int(rows[0]["followers"]) if rows else 0

    def _utc_today_start(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")

    def latest_metric_snapshot(self, post_id: str, snapshot: str) -> bool:
        rows = (
            self._client.table("metrics").select("id")
            .eq("post_id", post_id).eq("snapshot", snapshot).limit(1).execute().data
        )
        return bool(rows)

    def has_nightly_today(self, post_id: str) -> bool:
        rows = (
            self._client.table("metrics").select("id")
            .eq("post_id", post_id).eq("snapshot", "nightly")
            .gte("captured_at", self._utc_today_start()).limit(1).execute().data
        )
        return bool(rows)

    def has_follower_snapshot_today(self) -> bool:
        rows = (
            self._client.table("follower_snapshots").select("id")
            .eq("platform", "instagram")
            .gte("captured_at", self._utc_today_start()).limit(1).execute().data
        )
        return bool(rows)

    def select_approved_unposted_engagements(self) -> list[dict]:
        def build():
            return (self._client.table("engagements").select("*")
                    .eq("approval", "approved").is_("posted_at", "null").order("created_at"))
        return self._select_paged(build)

    def select_undigested_pending_engagements(self) -> list[dict]:
        def build():
            return (self._client.table("engagements").select("*")
                    .eq("approval", "pending").is_("digested_at", "null").order("created_at"))
        return self._select_paged(build)

    def count_engagements_today(self, kind: str) -> int:
        rows = (self._client.table("engagements").select("id")
                .eq("kind", kind).gte("created_at", self._utc_today_start()).execute().data)
        return len(rows)

    def current_strategy_weights(self) -> dict | None:
        rows = (
            self._client.table("strategy_weights").select("weights")
            .eq("current", True).order("computed_at", desc=True).limit(1).execute().data
        )
        return rows[0]["weights"] if rows else None

    def save_strategy_weights(self, weights: dict, note: str = "") -> dict:
        # Insert the new current row FIRST, then demote every other current row.
        # Ordering this way means there is never a window with zero current rows
        # (a crash mid-way leaves the new row live, not the strategy defaulted).
        row = self.insert("strategy_weights", {"current": True, "weights": weights, "note": note})
        self._client.table("strategy_weights").update({"current": False}) \
            .eq("current", True).neq("id", row["id"]).execute()
        return row
