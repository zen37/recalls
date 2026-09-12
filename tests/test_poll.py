import recalls.poll as poll_mod
from recalls.config import Config
from recalls.models import Alert
from recalls.poll import poll_once
from recalls.store import SqliteAlertStore as AlertStore


def _alert(guid: str) -> Alert:
    return Alert(
        guid=guid,
        title=f"recall {guid}",
        link=f"http://example.gov/{guid}",
        published="2026-09-11T22:15:00+00:00",
        summary="x",
        source="fda",
    )


class _FakeSource:
    name = "fake"
    country = "us"

    def __init__(self, alerts):
        self._alerts = alerts

    def poll(self, config):
        return list(self._alerts)


def _patch_feed(monkeypatch, alerts):
    # Replace the country's source list with a single fake source (offline).
    monkeypatch.setattr(poll_mod, "sources_for", lambda country: [_FakeSource(alerts)])


def test_cold_start_all_new_is_not_a_gap(tmp_path, monkeypatch):
    store = AlertStore(str(tmp_path / "r.db"))
    _patch_feed(monkeypatch, [_alert("a"), _alert("b")])

    result = poll_once(Config.from_env(), store)

    assert len(result.new) == 2
    assert result.possible_gap is False  # empty store -> all-new is expected


def test_all_new_against_nonempty_store_flags_gap(tmp_path, monkeypatch):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert("seed")])  # store now non-empty

    # Next poll returns a window with zero overlap with what we've stored.
    _patch_feed(monkeypatch, [_alert("x"), _alert("y")])
    result = poll_once(Config.from_env(), store)

    assert [a.guid for a in result.new] == ["x", "y"]
    assert result.possible_gap is True


def test_partial_overlap_is_not_a_gap(tmp_path, monkeypatch):
    store = AlertStore(str(tmp_path / "r.db"))
    _patch_feed(monkeypatch, [_alert("a"), _alert("b")])
    poll_once(Config.from_env(), store)

    # Re-poll: "b" is known, "c" is new -> normal steady state, no gap.
    _patch_feed(monkeypatch, [_alert("b"), _alert("c")])
    result = poll_once(Config.from_env(), store)

    assert [a.guid for a in result.new] == ["c"]
    assert result.possible_gap is False


def test_empty_feed_is_not_a_gap(tmp_path, monkeypatch):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert("seed")])
    _patch_feed(monkeypatch, [])
    result = poll_once(Config.from_env(), store)
    assert result.possible_gap is False
