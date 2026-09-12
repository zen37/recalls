from pathlib import Path

from recalls.sources.base import parse_rss as parse

FIXTURE = Path(__file__).parent / "fixtures" / "fda_sample.xml"


def _raw() -> bytes:
    return FIXTURE.read_bytes()


def test_parse_maps_every_item():
    alerts = parse(_raw(), source="fda")
    assert len(alerts) == 2


def test_parse_fields():
    first = parse(_raw(), source="fda")[0]
    assert first.title == "Acme Foods Recalls Bagged Spinach Due to Listeria"
    assert first.link == "http://www.fda.gov/safety/recalls/acme-spinach-listeria"
    assert first.guid == first.link  # permalink guid
    assert first.source == "fda"
    assert "Listeria" in first.summary


def test_publish_normalized_to_iso_utc():
    first = parse(_raw(), source="fda")[0]
    # Fri, 11 Sep 2026 18:15:00 EDT == 22:15:00 UTC
    assert first.published == "2026-09-11T22:15:00+00:00"


def test_parse_skips_entry_without_guid_or_link():
    raw = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel><title>t</title>
      <item><title>no id here</title><description>x</description></item>
    </channel></rss>"""
    assert parse(raw, source="fda") == []
