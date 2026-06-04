import os
import pytest
from unittest.mock import patch
from src.rakso.identity.parser import load_identity_pack
from pydantic import ValidationError

def _write_default_required_files(tmp_path):
    # Helper to create basic files to satisfy Pydantic models for other tests
    (tmp_path / "product.md").write_text("---\nname: 'Default'\ndescription: 'Def'\n---\n", encoding="utf-8")
    (tmp_path / "visual.md").write_text("---\nstyle: 'DefaultStyle'\n---\n", encoding="utf-8")
    (tmp_path / "voice.md").write_text("---\ntone: 'DefaultTone'\n---\n", encoding="utf-8")
    (tmp_path / "hard_limits.md").write_text("---\nbanned_words: []\n---\n", encoding="utf-8")

def test_identity_pack_load_happy_path(tmp_path):
    """Happy path: valid frontmatter is merged properly. Successfully loads all voice, visual, product, and limit attributes."""
    voice_file = tmp_path / "voice.md"
    voice_file.write_text("---\ntone: 'friendly'\nvocabulary: ['hey', 'hi']\n---\nSome text", encoding="utf-8")
    
    visual_file = tmp_path / "visual.md"
    visual_file.write_text("---\ncolor_palette: ['red']\nstyle: 'modern'\n---\n", encoding="utf-8")
    
    product_file = tmp_path / "product.md"
    product_file.write_text("---\nname: 'RaksoApp'\ndescription: 'An app for Rakso'\ntarget_audience: ['devs']\n---\n", encoding="utf-8")

    limits_file = tmp_path / "hard_limits.md"
    limits_file.write_text("---\nbanned_words: ['bad']\nveto_topics: ['politics']\n---\n", encoding="utf-8")
    
    pack = load_identity_pack(str(tmp_path))
    assert pack["voice"]["tone"] == "friendly"
    assert pack["voice"]["vocabulary"] == ["hey", "hi"]
    assert pack["visual"]["color_palette"] == ["red"]
    assert pack["visual"]["style"] == "modern"
    assert pack["product"]["name"] == "RaksoApp"
    assert pack["product"]["description"] == "An app for Rakso"
    assert pack["hard_limits"]["banned_words"] == ["bad"]

def test_identity_pack_load_edge_case(tmp_path):
    """Edge case: files with leading whitespaces, empty frontmatter, and scalar values."""
    _write_default_required_files(tmp_path)
    
    empty_file = tmp_path / "empty.md"
    empty_file.write_text("\n\n---\n---\n", encoding="utf-8")
    
    no_fm_file = tmp_path / "no_fm.md"
    no_fm_file.write_text("Just some text", encoding="utf-8")
    
    space_file = tmp_path / "voice.md"
    space_file.write_text("   \n\n---\ntone: 'formal'\n---\n", encoding="utf-8")

    pack = load_identity_pack(str(tmp_path))
    assert pack["voice"]["tone"] == "formal"
    assert pack["visual"]["style"] == "DefaultStyle"
    
def test_identity_pack_load_error_handling(tmp_path):
    """Error handling: scalar value instead of dict raises ValueError."""
    bad_file = tmp_path / "voice.md"
    bad_file.write_text("---\nscalar_string\n---\n", encoding="utf-8")
    
    with pytest.raises(ValueError, match="must be a dictionary"):
        load_identity_pack(str(tmp_path))

    # Also test invalid YAML syntax
    invalid_file = tmp_path / "visual.md"
    invalid_file.write_text("---\n[invalid\n---\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_identity_pack(str(tmp_path))
        
    # Also test incorrect type in sub-dictionary merge
    bad_merge = tmp_path / "product.md"
    bad_merge.write_text("---\nvoice: 'should_be_dict_but_is_string'\n---\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected dict for key"):
        load_identity_pack(str(tmp_path))
