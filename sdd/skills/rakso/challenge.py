import asyncio
import time
from src.rakso.agents.sub_agents import RAKSOCreativo, NeurofunnelSub, ModuleC
from src.rakso.orchestration.bridge import TheBridge
from src.rakso.orchestration.marketing_agent import MarketingAgent
from src.rakso.identity.models import IdentityPack, VoiceConfig, VisualConfig, ProductConfig, HardLimitsConfig
from src.rakso.adapters.llm import LLMAdapter

class MockLLM(LLMAdapter):
    def __init__(self, reject=False):
        self.reject = reject

    async def generate(self, prompt: str, **kwargs) -> str:
        await asyncio.sleep(0.5)
        if "Determine the funnel stage" in prompt:
            return "AWARENESS"
        if "core emotion and cognitive bias" in prompt:
            return '{"core_emotion": "joy", "cognitive_bias": "halo effect"}'
        if "Review the following copy" in prompt:
            if self.reject:
                return '{"is_approved": false, "verdict_reason": "Manipulative urgency"}'
            return '{"is_approved": true, "verdict_reason": "Looks good"}'
        return "This is a creative copy with guarantee."

async def test_concurrency():
    identity = IdentityPack(
        voice=VoiceConfig(tone="professional", vocabulary=["innovative"]),
        visual=VisualConfig(color_palette=["#000"], style="minimalist"),
        product=ProductConfig(name="RAKSO", description="OS", target_audience=["marketers"]),
        hard_limits=HardLimitsConfig(banned_words=["banned123"], veto_topics=["topicxyz"])
    )
    llm = MockLLM()
    
    creativo = RAKSOCreativo(llm, identity)
    neuro = NeurofunnelSub(llm, identity)
    module_c = ModuleC(llm, identity)
    bridge = TheBridge(llm, identity)
    
    agent = MarketingAgent(creativo, neuro, module_c, bridge)
    
    start = time.time()
    await agent.execute({"brief": "Test"})
    end = time.time()
    
    duration = end - start
    # Sub-agents take 0.5s each. The bridge takes 0.5s. Total sequential = 2.0s. Concurrency = ~1.0s.
    print(f"Concurrency Test Duration: {duration:.2f}s")
    if duration < 1.5:
        print("CONCURRENCY: PASS")
    else:
        print("CONCURRENCY: FAIL")

async def test_bridge_banned_word():
    identity = IdentityPack(
        voice=VoiceConfig(tone="professional", vocabulary=["innovative"]),
        visual=VisualConfig(color_palette=["#000"], style="minimalist"),
        product=ProductConfig(name="RAKSO", description="OS", target_audience=["marketers"]),
        hard_limits=HardLimitsConfig(banned_words=["guarantee"], veto_topics=[])
    )
    llm = MockLLM()
    bridge = TheBridge(llm, identity)
    
    is_app, reason = await bridge.evaluate({"copy": "This has a guarantee in it."})
    if not is_app and "Banned word" in reason:
        print("BRIDGE BANNED WORD: PASS")
    else:
        print("BRIDGE BANNED WORD: FAIL", is_app, reason)

async def test_bridge_llm_rejection():
    identity = IdentityPack(
        voice=VoiceConfig(tone="professional", vocabulary=["innovative"]),
        visual=VisualConfig(color_palette=["#000"], style="minimalist"),
        product=ProductConfig(name="RAKSO", description="OS", target_audience=["marketers"]),
        hard_limits=HardLimitsConfig(banned_words=[], veto_topics=[])
    )
    llm = MockLLM(reject=True)
    bridge = TheBridge(llm, identity)
    
    is_app, reason = await bridge.evaluate({"copy": "Normal copy."})
    if not is_app and "Manipulative" in reason:
        print("BRIDGE LLM REJECTION: PASS")
    else:
        print("BRIDGE LLM REJECTION: FAIL", is_app, reason)

async def main():
    await test_concurrency()
    await test_bridge_banned_word()
    await test_bridge_llm_rejection()

if __name__ == "__main__":
    asyncio.run(main())
