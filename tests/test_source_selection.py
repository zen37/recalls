import pytest

from recalls.sources import sources_for


def test_none_returns_all_us_sources():
    names = {s.name for s in sources_for("us")}
    assert "fda" in names


def test_all_is_the_same_as_none():
    assert [s.name for s in sources_for("us", "all")] == [
        s.name for s in sources_for("us")
    ]


def test_named_source_narrows_to_one():
    selected = sources_for("us", "fda")
    assert [s.name for s in selected] == ["fda"]


def test_unknown_source_errors_and_lists_available():
    with pytest.raises(ValueError, match="no source 'nope'"):
        sources_for("us", "nope")


def test_unknown_country_still_errors():
    with pytest.raises(ValueError, match="no sources configured for country"):
        sources_for("zz", "fda")
