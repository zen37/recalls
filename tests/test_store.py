from dataclasses import replace

from recalls.models import Alert
from recalls.store import SqliteAlertStore as AlertStore


def _alert(guid: str, published: str = "2026-09-11T22:15:00+00:00") -> Alert:
    return Alert(
        guid=guid,
        title=f"recall {guid}",
        link=f"http://example.gov/{guid}",
        published=published,
        summary="because reasons",
        source="fda",
    )


def test_sync_reports_only_unseen_as_new(tmp_path):
    store = AlertStore(str(tmp_path / "r.db"))

    first = store.sync([_alert("a"), _alert("b")])
    assert {a.guid for a in first.new} == {"a", "b"}
    assert first.updated == []

    # Re-poll the same rolling window plus one genuinely new item.
    second = store.sync([_alert("a"), _alert("b"), _alert("c")])
    assert [a.guid for a in second.new] == ["c"]
    assert second.updated == []  # a, b unchanged -> not updated

    assert store.count() == 3


def test_sync_detects_content_change_as_updated(tmp_path):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert("a")])

    # Same guid, changed summary (e.g. FDA expanded the affected lots).
    changed = replace(_alert("a"), summary="EXPANDED: now includes lot 42")
    result = store.sync([changed])

    assert result.new == []
    assert [a.guid for a in result.updated] == ["a"]
    assert store.count() == 1  # updated in place, not duplicated
    # The stored content reflects the update.
    assert "EXPANDED" in store.recent()[0].summary


def test_sync_identical_content_is_noop(tmp_path):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert("a")])
    result = store.sync([_alert("a")])  # byte-identical
    assert result.new == []
    assert result.updated == []


def test_recent_orders_by_published_desc(tmp_path):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync(
        [
            _alert("old", "2026-09-01T00:00:00+00:00"),
            _alert("new", "2026-09-11T00:00:00+00:00"),
        ]
    )
    recent = store.recent()
    assert [a.guid for a in recent] == ["new", "old"]


def test_recent_limit(tmp_path):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert(str(i), f"2026-09-{i:02d}T00:00:00+00:00") for i in range(1, 6)])
    assert len(store.recent(limit=2)) == 2


def test_empty_sync_is_noop(tmp_path):
    store = AlertStore(str(tmp_path / "r.db"))
    result = store.sync([])
    assert result.new == []
    assert result.updated == []
    assert store.count() == 0


def test_history_records_new_then_update(tmp_path):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert("a", published="2026-09-01T00:00:00+00:00")])
    store.sync([replace(_alert("a"), summary="EXPANDED lots")])
    store.sync([_alert("a")])  # revert-ish: another content change -> another event

    timeline = store.history(guid="a")
    # newest first: two updates + the original 'new'
    assert [e.change_type for e in timeline] == ["updated", "updated", "new"]
    assert timeline[-1].change_type == "new"
    # the middle event captured the expanded-lots snapshot
    assert timeline[1].summary == "EXPANDED lots"


def test_history_unchanged_adds_no_event(tmp_path):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert("a")])
    store.sync([_alert("a")])  # identical
    assert len(store.history(guid="a")) == 1  # only the original 'new'


def test_history_across_guids_newest_first(tmp_path):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert("a")])
    store.sync([_alert("b")])
    all_events = store.history()
    assert [e.guid for e in all_events] == ["b", "a"]
