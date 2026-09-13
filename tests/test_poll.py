import recalls.poll as poll_mod
from recalls.config import Config
from recalls.landing import NullLanding
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

    def fetch(self, config):
        return b"<rss/>"

    def parse(self, raw):
        return list(self._alerts)


def _patch_feed(monkeypatch, alerts):
    # Replace the country's source list with a single fake source (offline).
    monkeypatch.setattr(
        poll_mod, "sources_for", lambda country, source=None: [_FakeSource(alerts)]
    )


def test_cold_start_all_new_is_not_a_gap(tmp_path, monkeypatch):
    store = AlertStore(str(tmp_path / "r.db"))
    _patch_feed(monkeypatch, [_alert("a"), _alert("b")])

    result = poll_once(Config.from_env(), store, NullLanding())

    assert len(result.new) == 2
    assert result.possible_gap is False  # empty store -> all-new is expected


def test_all_new_against_nonempty_store_flags_gap(tmp_path, monkeypatch):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert("seed")])  # store now non-empty

    # Next poll returns a window with zero overlap with what we've stored.
    _patch_feed(monkeypatch, [_alert("x"), _alert("y")])
    result = poll_once(Config.from_env(), store, NullLanding())

    assert [a.guid for a in result.new] == ["x", "y"]
    assert result.possible_gap is True


def test_partial_overlap_is_not_a_gap(tmp_path, monkeypatch):
    store = AlertStore(str(tmp_path / "r.db"))
    _patch_feed(monkeypatch, [_alert("a"), _alert("b")])
    poll_once(Config.from_env(), store, NullLanding())

    # Re-poll: "b" is known, "c" is new -> normal steady state, no gap.
    _patch_feed(monkeypatch, [_alert("b"), _alert("c")])
    result = poll_once(Config.from_env(), store, NullLanding())

    assert [a.guid for a in result.new] == ["c"]
    assert result.possible_gap is False


def test_empty_feed_is_not_a_gap(tmp_path, monkeypatch):
    store = AlertStore(str(tmp_path / "r.db"))
    store.sync([_alert("seed")])
    _patch_feed(monkeypatch, [])
    result = poll_once(Config.from_env(), store, NullLanding())
    assert result.possible_gap is False


class _BrokenSource:
    """A source whose fetch always fails (e.g. a CDN 403)."""

    name = "broken"
    country = "us"

    def fetch(self, config):
        raise RuntimeError("403 Forbidden")

    def parse(self, raw):  # pragma: no cover - never reached
        return []


def test_one_source_failing_does_not_abort_the_poll(tmp_path, monkeypatch):
    # Healthy source first, broken source second: the broken one must not
    # suppress the healthy one's alerts.
    good = _FakeSource([_alert("a"), _alert("b")])
    monkeypatch.setattr(
        poll_mod, "sources_for", lambda country, source=None: [good, _BrokenSource()]
    )
    store = AlertStore(str(tmp_path / "r.db"))

    result = poll_once(Config.from_env(), store, NullLanding())

    assert [a.guid for a in result.new] == ["a", "b"]  # healthy feed still stored
    assert result.fetched == 2
    assert len(result.errors) == 1
    assert result.errors[0].startswith("broken: ")


def test_broken_source_first_still_runs_the_rest(tmp_path, monkeypatch):
    # Order independence: a failure in the first source must not skip later ones.
    good = _FakeSource([_alert("a")])
    monkeypatch.setattr(
        poll_mod, "sources_for", lambda country, source=None: [_BrokenSource(), good]
    )
    store = AlertStore(str(tmp_path / "r.db"))

    result = poll_once(Config.from_env(), store, NullLanding())

    assert [a.guid for a in result.new] == ["a"]
    assert len(result.errors) == 1


def test_all_sources_failing_yields_errors_and_no_fetch(tmp_path, monkeypatch):
    monkeypatch.setattr(
        poll_mod, "sources_for", lambda country, source=None: [_BrokenSource(), _BrokenSource()]
    )
    store = AlertStore(str(tmp_path / "r.db"))

    result = poll_once(Config.from_env(), store, NullLanding())

    assert result.fetched == 0
    assert result.new == []
    assert len(result.errors) == 2
