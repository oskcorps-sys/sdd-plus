import os
import yaml
from typing import Dict, Any
from .models import IdentityPack

def load_identity_pack(vault_path: str) -> Dict[str, Any]:
    """
    Load identity pack from an Obsidian vault.
    Reads markdown frontmatter and validates using IdentityPack schema.
    Returns a dictionary of the validated data.
    """
    data = {
        "voice": {},
        "visual": {},
        "product": {},
        "hard_limits": {}
    }

    if os.path.exists(vault_path):
        for root, _, files in os.walk(vault_path):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    frontmatter = _extract_frontmatter(file_path)
                    
                    fm_copy = dict(frontmatter)
                    
                    # Merge frontmatter based on predefined keys
                    for key in data.keys():
                        if key in fm_copy:
                            val = fm_copy.pop(key)
                            if isinstance(val, dict):
                                data[key].update(val)
                            elif val is not None:
                                raise ValueError(f"Expected dict for key '{key}' in {file_path}")
                    
                    # If the file name itself is a category, e.g., voice.md
                    category = os.path.splitext(file)[0].lower()
                    if category in data:
                        # Assuming the remaining frontmatter belongs to that category
                        data[category].update(fm_copy)
                        
    # Ensure defaults or required fields are somewhat populated for missing files
    # The pydantic model will validate and set defaults
    pack = IdentityPack(**data)
    
    return pack.model_dump()

def _extract_frontmatter(file_path: str) -> Dict[str, Any]:
    """Extract YAML frontmatter from a markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Error reading file {file_path}: {str(e)}")

    stripped_content = content.lstrip()
    if stripped_content.startswith('---'):
        parts = stripped_content.split('---', 2)
        if len(parts) >= 3:
            yaml_content = parts[1]
            try:
                parsed = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {file_path}: {str(e)}")
            
            if parsed is None:
                return {}
            if not isinstance(parsed, dict):
                raise ValueError(f"Frontmatter in {file_path} must be a dictionary, got {type(parsed).__name__}.")
            return parsed
    return {}
