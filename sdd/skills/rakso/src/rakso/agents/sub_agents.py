import json
from .base import SubAgent
from typing import Dict, Any

class RAKSOCreativo(SubAgent):
    """Handles creative copy generation based on visual and voice identity."""
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            f"Generate creative copy based on the following context:\n"
            f"{json.dumps(context)}\n"
            f"Use the following voice tone: {self.identity.voice.tone}\n"
            f"Use the following vocabulary: {', '.join(self.identity.voice.vocabulary)}\n"
            f"Please return only the copy."
        )
        response = await self.llm.generate(prompt)
        return {"copy": response.strip()}

class NeurofunnelSub(SubAgent):
    """Maps copy to funnel stages (AWARENESS, CONSIDERATION, CONVERSION)."""
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            f"Determine the funnel stage (AWARENESS, CONSIDERATION, CONVERSION) for the following context:\n"
            f"{json.dumps(context)}\n"
            f"Respond with only the funnel stage name."
        )
        response = await self.llm.generate(prompt)
        stage = response.strip()
        return {"funnel_stage": stage}

class ModuleC(SubAgent):
    """Applies cognitive biases and core emotion enhancements."""
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            f"Determine the core emotion and cognitive bias for the following context:\n"
            f"{json.dumps(context)}\n"
            f"Respond in JSON format with keys: 'core_emotion' and 'cognitive_bias'."
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
                result = {"result": result}
        except json.JSONDecodeError:
            result = {"core_emotion": "unknown", "cognitive_bias": "unknown"}
        return result
