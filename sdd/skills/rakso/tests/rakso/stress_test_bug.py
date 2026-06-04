import pytest
import os
from src.rakso.identity.parser import _extract_frontmatter

def test_parser_scalar_crash(tmp_path):
    scalar_file = tmp_path / "scalar.md"
    scalar_file.write_text("---\nJust a string instead of dict\n---\nBody here", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a dictionary"):
        _extract_frontmatter(str(scalar_file))

def test_parser_masking_exceptions(tmp_path):
    bad_yaml = tmp_path / "bad.md"
    bad_yaml.write_text("---\nvoice:\n  - [\n---\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        _extract_frontmatter(str(bad_yaml))
