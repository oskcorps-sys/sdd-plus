import pytest
from src.rakso.identity.parser import _extract_frontmatter

def test_parser_whitespace_sensitivity(tmp_path):
    ws_file = tmp_path / "ws.md"
    ws_file.write_text("   \n\n  ---\nvoice:\n  tone: bold\n---\ncontent", encoding="utf-8")
    res = _extract_frontmatter(str(ws_file))
    assert res == {"voice": {"tone": "bold"}}
