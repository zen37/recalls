from pathlib import Path

from recalls.landing import LocalDirLanding


def _gz_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.xml.gz"))


def test_lands_raw_bytes(tmp_path):
    landing = LocalDirLanding(str(tmp_path))
    assert landing.land("us", "fda", b"<rss>one</rss>") is True
    files = _gz_files(tmp_path)
    assert len(files) == 1
    # stored under <root>/<country>/<source>/
    assert files[0].parent == tmp_path / "us" / "fda"


def test_unchanged_content_is_skipped(tmp_path):
    landing = LocalDirLanding(str(tmp_path))
    assert landing.land("us", "fda", b"same") is True
    assert landing.land("us", "fda", b"same") is False  # deduped
    assert len(_gz_files(tmp_path)) == 1


def test_changed_content_lands_again(tmp_path):
    landing = LocalDirLanding(str(tmp_path))
    assert landing.land("us", "fda", b"v1") is True
    assert landing.land("us", "fda", b"v2") is True
    assert len(_gz_files(tmp_path)) == 2


def test_separate_country_source_are_independent(tmp_path):
    landing = LocalDirLanding(str(tmp_path))
    assert landing.land("us", "fda", b"x") is True
    assert landing.land("ca", "cfia", b"x") is True  # same bytes, different bucket
    assert len(_gz_files(tmp_path)) == 2
