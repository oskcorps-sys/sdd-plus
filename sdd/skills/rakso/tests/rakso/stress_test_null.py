import pytest
from src.rakso.identity.parser import _extract_frontmatter

def test_parser_null_frontmatter(tmp_path):
    null_fm = tmp_path / "null.md"
    null_fm.write_text("---\n---\nbody", encoding="utf-8")
    res = _extract_frontmatter(str(null_fm))
    assert res == {}

def test_parser_explicit_null(tmp_path):
    null_fm = tmp_path / "explicit_null.md"
    null_fm.write_text("---\nnull\n---\nbody", encoding="utf-8")
    res = _extract_frontmatter(str(null_fm))
    assert res == {}
