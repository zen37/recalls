from pathlib import Path

from recalls.sources.base import parse_rss as parse
from recalls.sources.us import SOURCES
from recalls.sources.us.fsis import FsisSource

FIXTURE = Path(__file__).parent / "fixtures" / "fsis_sample.xml"


def _raw() -> bytes:
    return FIXTURE.read_bytes()


def test_parse_maps_every_item():
    alerts = parse(_raw(), source="fsis")
    assert len(alerts) == 2


def test_parse_fields():
    first = parse(_raw(), source="fsis")[0]
    assert first.title.startswith("Brazilian Taste Recalls Frozen Chicken")
    assert first.link == (
        "http://www.fsis.usda.gov/recalls-alerts/"
        "brazilian-taste-recalls-frozen-chicken-and-beef-croquette-products"
    )
    assert first.guid == first.link  # permalink guid
    assert first.source == "fsis"
    assert "undeclared allergen" in first.summary


def test_publish_normalized_to_iso_utc():
    first = parse(_raw(), source="fsis")[0]
    # Fri, 11 Sep 2026 12:00:00 +0000
    assert first.published == "2026-09-11T12:00:00+00:00"


def test_source_connector_parses_fixture():
    # The FsisSource uses the shared RSS parser with source="fsis".
    alerts = FsisSource().parse(_raw())
    assert [a.source for a in alerts] == ["fsis", "fsis"]


def test_fsis_registered_for_us():
    names = {s.name for s in SOURCES}
    assert {"fda", "fsis"} <= names
