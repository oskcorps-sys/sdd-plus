import asyncio
from typing import Dict, Any
from src.rakso.agents.sub_agents import RAKSOCreativo, NeurofunnelSub, ModuleC
from src.rakso.orchestration.bridge import TheBridge

class MarketingAgent:
    def __init__(self, creativo: RAKSOCreativo, neuro: NeurofunnelSub, module_c: ModuleC, bridge: TheBridge):
        self.creativo = creativo
        self.neuro = neuro
        self.module_c = module_c
        self.bridge = bridge
        
    async def execute(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Fan-out to sub-agents via asyncio.gather, then funnel through TheBridge."""
        # Execute sub-agents concurrently
        creativo_task = self.creativo.execute(brief)
        neuro_task = self.neuro.execute(brief)
        module_c_task = self.module_c.execute(brief)
        
        creativo_res, neuro_res, module_c_res = await asyncio.gather(
            creativo_task, neuro_task, module_c_task
        )
        
        # Aggregate results
        payload = {
            "copy": creativo_res.get("copy", ""),
            "stage_metadata": {
                "funnel_stage": neuro_res.get("funnel_stage", "UNKNOWN"),
                "core_emotion": module_c_res.get("core_emotion", "unknown"),
                "cognitive_bias": module_c_res.get("cognitive_bias", "unknown")
            }
        }
        
        # Evaluate through The Bridge
        is_approved, verdict_reason = await self.bridge.evaluate(payload)
        
        if is_approved:
            payload["bridge_verdict"] = "APPROVED"
        else:
            payload["bridge_verdict"] = "REJECTED"
            payload["bridge_reason"] = verdict_reason
            
        return payload
