import asyncio
import time
from src.rakso.agents.sub_agents import RAKSOCreativo, NeurofunnelSub, ModuleC
from src.rakso.orchestration.bridge import TheBridge
from src.rakso.orchestration.marketing_agent import MarketingAgent
from src.rakso.identity.models import IdentityPack, VoiceConfig, VisualConfig, ProductConfig, HardLimitsConfig
from src.rakso.adapters.llm import LLMAdapter

class DelayLLMAdapter(LLMAdapter):
    def __init__(self, delay=2.0, response_content=""):
        self.delay = delay
        self.response_content = response_content
        self.calls = 0

    async def generate(self, prompt: str, **kwargs) -> str:
        self.calls += 1
        await asyncio.sleep(self.delay)
        return self.response_content

async def test_concurrency():
    identity = IdentityPack(
        voice=VoiceConfig(tone="professional", vocabulary=["innovative"]),
        visual=VisualConfig(color_palette=["#000000"], style="minimalist"),
        product=ProductConfig(name="RAKSO", description="OS", target_audience=["marketers"]),
        hard_limits=HardLimitsConfig(banned_words=["guarantee", "miracle"], veto_topics=["politics", "religion"])
    )
    
    # We want to trace when each sub-agent starts and finishes.
    class TrackingLLM(LLMAdapter):
        def __init__(self, delay=2.0):
            self.delay = delay
            
        async def generate(self, prompt: str, **kwargs) -> str:
            start = time.time()
            print(f"Start generate: {prompt[:30]}... at {start}")
            await asyncio.sleep(self.delay)
            end = time.time()
            print(f"End generate: {prompt[:30]}... at {end}")
            if "core_emotion" in prompt:
                return '{"core_emotion": "joy", "cognitive_bias": "halo effect"}'
            if "funnel_stage" in prompt:
                return "AWARENESS"
            if "manipulative" in prompt:
                # The bridge prompt
                return '{"is_approved": true, "verdict_reason": "Approved"}'
            return "Some generated copy."

    llm = TrackingLLM(delay=1.0)
    creativo = RAKSOCreativo(llm, identity)
    neuro = NeurofunnelSub(llm, identity)
    module_c = ModuleC(llm, identity)
    bridge = TheBridge(llm, identity)
    
    agent = MarketingAgent(creativo, neuro, module_c, bridge)
    
    print("Testing concurrency...")
    start = time.time()
    res = await agent.execute({"brief": "Make it go viral"})
    end = time.time()
    print(f"Total time: {end - start:.2f}s (Should be ~2s if concurrent, ~4s if not because Bridge is sequential)")
    print("Result:", res)


async def test_bridge():
    identity = IdentityPack(
        voice=VoiceConfig(tone="professional", vocabulary=["innovative"]),
        visual=VisualConfig(color_palette=["#000000"], style="minimalist"),
        product=ProductConfig(name="RAKSO", description="OS", target_audience=["marketers"]),
        hard_limits=HardLimitsConfig(banned_words=["guarantee", "miracle"], veto_topics=["politics", "religion"])
    )
    
    class BridgeLLM(LLMAdapter):
        async def generate(self, prompt: str, **kwargs) -> str:
            if "manipulative tactics" in prompt:
                return '{"is_approved": false, "verdict_reason": "Excessive hype and manipulation"}'
            return '{"core_emotion": "joy", "cognitive_bias": "halo effect"}'
            
    llm = BridgeLLM()
    bridge = TheBridge(llm, identity)
    
    print("\nTesting Banned Word:")
    payload1 = {"copy": "We guarantee you success!"}
    res1, reason1 = await bridge.evaluate(payload1)
    print("Approved:", res1, "Reason:", reason1)

    print("\nTesting Veto Topic:")
    payload2 = {"copy": "Let's talk about politics today."}
    res2, reason2 = await bridge.evaluate(payload2)
    print("Approved:", res2, "Reason:", reason2)
    
    print("\nTesting LLM Manipulation Catch:")
    payload3 = {"copy": "This is totally legit, hurry before time runs out!"}
    res3, reason3 = await bridge.evaluate(payload3)
    print("Approved:", res3, "Reason:", reason3)

if __name__ == "__main__":
    asyncio.run(test_concurrency())
    asyncio.run(test_bridge())
