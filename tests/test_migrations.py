"""Tests for the migration apply helper.

These cover the CLI surface (argument parsing, dry-run listing) and the
psql / RPC dispatch — we don't hit a real DB. Real migrations are
exercised on the live Supabase project.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from db.migrations import apply as apply_mod
from db.migrations.apply import _apply_via_psql, _apply_via_rpc, _iter_migrations, main


# ── CLI surface ───────────────────────────────────────────────────────────────

class TestIterMigrations:
    def test_returns_sorted_sql_files(self):
        files = _iter_migrations(None)
        assert all(f.suffix == ".sql" for f in files)
        # Filename sort must be deterministic; alphabetical == chronological
        # when filenames are zero-padded dates (which ours are).
        names = [f.name for f in files]
        assert names == sorted(names)

    def test_only_glob_filters(self):
        files = _iter_migrations("2026_*")
        assert all(f.name.startswith("2026_") for f in files)

    def test_no_match_returns_empty(self):
        files = _iter_migrations("9999_*")
        assert files == []


class TestDryRun:
    def test_dry_run_prints_names_exits_zero(self, capsys):
        rc = main(["--dry-run"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "2026_08_17_competitors_newsletter.sql" in captured.out


class TestMainFailure:
    def test_exit_one_on_first_apply_failure(self):
        with patch("db.migrations.apply.apply_one", return_value=False):
            rc = main([])
        assert rc == 1

    def test_exit_zero_when_all_apply(self):
        with patch("db.migrations.apply.apply_one", return_value=True):
            rc = main([])
        assert rc == 0


# ── apply_via_psql ────────────────────────────────────────────────────────────

class TestApplyViaPsql:
    def test_missing_env_returns_false(self):
        with patch.dict(os.environ, {}, clear=True):
            ok, msg = _apply_via_psql(Path("/tmp/anything.sql"))
        assert ok is False
        assert "SUPABASE_DB_URL not set" in msg

    def test_psql_not_installed_returns_false(self):
        with patch.dict(os.environ, {"SUPABASE_DB_URL": "postgres://x"}):
            with patch("db.migrations.apply.subprocess.run",
                       side_effect=FileNotFoundError):
                ok, msg = _apply_via_psql(Path("/tmp/anything.sql"))
        assert ok is False
        assert "psql not installed" in msg

    def test_psql_success_returns_true(self):
        fake = MagicMock(returncode=0)
        fake.stdout = "NOTICE:  applied\n"
        fake.stderr = ""
        with patch.dict(os.environ, {"SUPABASE_DB_URL": "postgres://x"}):
            with patch("db.migrations.apply.subprocess.run", return_value=fake):
                ok, msg = _apply_via_psql(Path("/tmp/anything.sql"))
        assert ok is True
        assert "applied" in msg

    def test_psql_nonzero_returns_false(self):
        fake = MagicMock(returncode=1)
        fake.stdout = ""
        fake.stderr = "ERROR: syntax error"
        with patch.dict(os.environ, {"SUPABASE_DB_URL": "postgres://x"}):
            with patch("db.migrations.apply.subprocess.run", return_value=fake):
                ok, msg = _apply_via_psql(Path("/tmp/anything.sql"))
        assert ok is False
        assert "syntax error" in msg


# ── apply_via_rpc fallback ────────────────────────────────────────────────────

class TestApplyViaRpc:
    def test_missing_env_returns_false(self):
        with patch.dict(os.environ, {}, clear=True):
            ok, msg = _apply_via_rpc(Path("/tmp/anything.sql"))
        assert ok is False
        assert "not set" in msg

    def test_rpc_exception_returns_false(self):
        # Patch supabase import inside the function so we don't depend on
        # the module-level import at test time.
        fake_client = MagicMock()
        fake_client.rpc.return_value.execute.side_effect = RuntimeError("nope")
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_KEY": "key",
        }):
            with patch("supabase.create_client", return_value=fake_client):
                # Path.read_text is called first; create a real tmp file.
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tf:
                    tf.write(b"-- stub")
                    tmp = Path(tf.name)
                try:
                    ok, msg = _apply_via_rpc(tmp)
                finally:
                    tmp.unlink()
        assert ok is False
        assert "nope" in msg
