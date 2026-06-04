from abc import ABC, abstractmethod
from typing import Dict, Any
from src.rakso.adapters.llm import LLMAdapter
from src.rakso.identity.models import IdentityPack

class SubAgent(ABC):
    def __init__(self, llm_adapter: LLMAdapter, identity: IdentityPack):
        self.llm = llm_adapter
        self.identity = identity

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent task and return structured output."""
        pass
