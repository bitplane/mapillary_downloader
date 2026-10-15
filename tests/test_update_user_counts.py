"""Profile totals preserve regional counts and allow interrupted updates to resume."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from mapillary_downloader import client_web

spec = importlib.util.spec_from_file_location(
    "update_user_counts", Path(__file__).parents[1] / "scripts" / "update-user-counts.py"
)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)


def test_updates_all_entries_and_pauses(tmp_path, monkeypatch):
    filename = tmp_path / "leaderboards.json"

    def row(username, count):
        return {"user": {"username": username, "id": username}, "count": count}

    original = {
        "one": {"name": "One", "leaderboard": {"lifetime": [row("a", 1), row("b", 2)], "week": [row("a", 3)]}},
        "two": {"name": "Two", "leaderboard": {"lifetime": [row("a", 4)], "month": [row("a", 5)]}},
    }
    filename.write_text(json.dumps(original))
    sleep = Mock()
    monkeypatch.setattr(script.time, "sleep", sleep)

    def fetch(username):
        if username == "b":
            saved = json.loads(filename.read_text())
            assert saved["two"]["leaderboard"]["lifetime"][0]["total_count"] == 100
        return {"a": 100, "b": 200}[username]

    monkeypatch.setattr(script, "get_profile_image_count", fetch)
    assert script.main(["a", "a", "b", "--file", str(filename)]) == 0
    result = json.loads(filename.read_text())
    assert [r["total_count"] for r in result["one"]["leaderboard"]["lifetime"]] == [100, 200]
    assert script.main(["a", "b", "--file", str(filename)]) == 0
    sleep.assert_called_once_with(5.0)
    for location in result.values():
        for entry in location["leaderboard"]["lifetime"]:
            del entry["total_count"]
    assert result == original
    assert result["one"]["leaderboard"]["week"] == original["one"]["leaderboard"]["week"]
    assert result["two"]["leaderboard"]["month"] == original["two"]["leaderboard"]["month"]
    sleep.assert_called_once_with(5.0)


def test_failed_lookup_keeps_cache(tmp_path, monkeypatch):
    filename = tmp_path / "leaderboards.json"
    filename.write_text('{"x": {"leaderboard": {"lifetime": [{"user": {"username": "a"}, "count": 42}]}}}')
    original = filename.read_bytes()
    monkeypatch.setattr(script, "call_with_retry", lambda *a: None)
    assert script.main(["a", "missing", "--file", str(filename)]) == 1
    assert filename.read_bytes() == original


@pytest.mark.parametrize("profile", [None, {"stats": None}, {"stats": {"images": "42"}}, {"stats": {"images": -1}}])
def test_profile_rejects_unknown_counts(monkeypatch, profile):
    response = Mock()
    response.json.return_value = {"data": {"user_by_username": profile}}
    monkeypatch.setattr(client_web, "get_web_token", lambda: "token")
    monkeypatch.setattr(client_web.requests, "get", lambda *a, **kw: response)
    with pytest.raises(ValueError):
        client_web.get_profile_image_count("a")


def test_profile_accepts_zero(monkeypatch):
    response = Mock()
    response.json.return_value = {"data": {"user_by_username": {"stats": {"images": 0}}}}
    monkeypatch.setattr(client_web, "get_web_token", lambda: "token")
    monkeypatch.setattr(client_web.requests, "get", lambda *a, **kw: response)
    assert client_web.get_profile_image_count("a") == 0


def test_get_users_prefers_total_and_excludes_archived(tmp_path):
    import os
    import subprocess
    import sys

    cache = tmp_path / "mapillary_downloader"
    cache.mkdir()
    rows = [
        {"user": {"username": "updated"}, "count": 10, "total_count": 100},
        {"user": {"username": "pending"}, "count": 20},
        {"user": {"username": "empty"}, "count": 5, "total_count": 0},
        {"user": {"username": "archived"}, "count": 1, "total_count": 200},
    ]
    (cache / "leaderboards.json").write_text(json.dumps({"x": {"name": "X", "leaderboard": {"lifetime": rows}}}))
    (cache / ".stats.json").write_text(json.dumps({"item": {"username": "archived"}}))
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[1] / "scripts" / "get-users.py"), "--exclude-archived"],
        env={**os.environ, "XDG_CACHE_HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == "0\tempty\n20\tpending\n100\tupdated\n"
