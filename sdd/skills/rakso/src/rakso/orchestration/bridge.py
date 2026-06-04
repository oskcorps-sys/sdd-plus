import json
import re
from typing import Dict, Any, Tuple
from src.rakso.adapters.llm import LLMAdapter
from src.rakso.identity.models import IdentityPack

class TheBridge:
    """Policy gate with absolute veto authority over outputs."""
    def __init__(self, llm_adapter: LLMAdapter, identity: IdentityPack):
        self.llm = llm_adapter
        self.identity = identity

    async def evaluate(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluates payload against manipulative copy and policy violations.
        Returns (is_approved, verdict_reason).
        """
        copy_text = payload.get("copy", "").lower()
        
        # String matching for banned words
        for word in self.identity.hard_limits.banned_words:
            if re.search(r'\b' + re.escape(word) + r'\b', copy_text, re.IGNORECASE):
                return False, f"Banned word found: {word}"
                
        # String matching for veto topics
        for topic in self.identity.hard_limits.veto_topics:
            if topic.lower() in copy_text:
                return False, f"Veto topic found: {topic}"
                
        # LLM semantic check for manipulative copy
        prompt = (
            f"Review the following copy for manipulative tactics, excessive hype, or policy violations:\n"
            f"Copy: {copy_text}\n"
            f"Does this copy use manipulative tactics or violate ethical marketing rules? "
            f"Respond with a JSON object containing keys: 'is_approved' (boolean) and 'verdict_reason' (string)."
        )
        response = await self.llm.generate(prompt)
        text = response.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            result = json.loads(text)
            if not isinstance(result, dict):
                return False, "Invalid LLM response format"
            is_approved = bool(result.get("is_approved", False))
            verdict_reason = str(result.get("verdict_reason", "LLM verdict"))
            if not is_approved:
                return False, verdict_reason
        except Exception as e:
            return False, "Fail-closed due to exception or invalid format"

        return True, "Approved"
