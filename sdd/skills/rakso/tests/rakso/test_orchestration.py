import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from src.rakso.agents.sub_agents import RAKSOCreativo, NeurofunnelSub, ModuleC
from src.rakso.orchestration.bridge import TheBridge
from src.rakso.orchestration.marketing_agent import MarketingAgent
from src.rakso.identity.models import IdentityPack, VoiceConfig, VisualConfig, ProductConfig, HardLimitsConfig
from src.rakso.adapters.llm import LLMAdapter

@pytest.fixture
def mock_identity():
    return IdentityPack(
        voice=VoiceConfig(tone="professional", vocabulary=["innovative", "seamless"]),
        visual=VisualConfig(color_palette=["#000000"], style="minimalist"),
        product=ProductConfig(name="RAKSO", description="OS for marketing", target_audience=["marketers"]),
        hard_limits=HardLimitsConfig(banned_words=["guarantee", "miracle"], veto_topics=["politics", "religion"])
    )

@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=LLMAdapter)
    llm.generate = AsyncMock()
    return llm

# --- Parallel Execution Tests ---
@pytest.mark.asyncio
async def test_marketing_agent_parallel_execution(mock_identity, mock_llm):
    """Prove asyncio.gather executes them concurrently."""
    creativo = RAKSOCreativo(mock_llm, mock_identity)
    neuro = NeurofunnelSub(mock_llm, mock_identity)
    module_c = ModuleC(mock_llm, mock_identity)
    bridge = TheBridge(mock_llm, mock_identity)
    
    # Mock bridge evaluation
    bridge.evaluate = AsyncMock(return_value=(True, "Approved"))

    # We mock execute directly to sleep
    async def slow_execute(*args, **kwargs):
        await asyncio.sleep(0.1)
        return {"result": "ok"}
        
    creativo.execute = AsyncMock(side_effect=slow_execute)
    neuro.execute = AsyncMock(side_effect=slow_execute)
    module_c.execute = AsyncMock(side_effect=slow_execute)
    
    agent = MarketingAgent(creativo, neuro, module_c, bridge)
    
    start_time = time.time()
    await agent.execute({"objective": "Test"})
    end_time = time.time()
    
    duration = end_time - start_time
    assert duration < 0.25  # Should be ~0.1, not 0.3
    
@pytest.mark.asyncio
async def test_marketing_agent_aggregates_results(mock_identity, mock_llm):
    """Test that it correctly aggregates results from sub-agents."""
    creativo = RAKSOCreativo(mock_llm, mock_identity)
    neuro = NeurofunnelSub(mock_llm, mock_identity)
    module_c = ModuleC(mock_llm, mock_identity)
    bridge = TheBridge(mock_llm, mock_identity)
    
    creativo.execute = AsyncMock(return_value={"copy": "Test copy"})
    neuro.execute = AsyncMock(return_value={"funnel_stage": "AWARENESS"})
    module_c.execute = AsyncMock(return_value={"core_emotion": "joy", "cognitive_bias": "halo effect"})
    bridge.evaluate = AsyncMock(return_value=(True, "Approved"))
    
    agent = MarketingAgent(creativo, neuro, module_c, bridge)
    payload = await agent.execute({"objective": "Test"})
    
    assert payload["copy"] == "Test copy"
    assert payload["stage_metadata"]["funnel_stage"] == "AWARENESS"
    assert payload["stage_metadata"]["core_emotion"] == "joy"
    assert payload["stage_metadata"]["cognitive_bias"] == "halo effect"
    assert payload["bridge_verdict"] == "APPROVED"

@pytest.mark.asyncio
async def test_marketing_agent_graceful_rejection(mock_identity, mock_llm):
    """Test the rejection flow matches CONTRACT expectations."""
    creativo = RAKSOCreativo(mock_llm, mock_identity)
    neuro = NeurofunnelSub(mock_llm, mock_identity)
    module_c = ModuleC(mock_llm, mock_identity)
    bridge = TheBridge(mock_llm, mock_identity)
    
    creativo.execute = AsyncMock(return_value={"copy": "Bad copy"})
    neuro.execute = AsyncMock(return_value={"funnel_stage": "AWARENESS"})
    module_c.execute = AsyncMock(return_value={"core_emotion": "anger", "cognitive_bias": "none"})
    
    bridge.evaluate = AsyncMock(return_value=(False, "Banned word found: guarantee"))
    
    agent = MarketingAgent(creativo, neuro, module_c, bridge)
    payload = await agent.execute({"objective": "Test"})
    
    assert payload["bridge_verdict"] == "REJECTED"
    assert payload["bridge_reason"] == "Banned word found: guarantee"


# --- The Bridge Veto Tests ---
@pytest.mark.asyncio
async def test_the_bridge_banned_words_veto(mock_identity, mock_llm):
    bridge = TheBridge(mock_llm, mock_identity)
    payload = {"copy": "We guarantee you will see a miracle."}
    
    is_approved, reason = await bridge.evaluate(payload)
    
    assert not is_approved
    assert "Banned word found: guarantee" in reason

@pytest.mark.asyncio
async def test_the_bridge_veto_topics_veto(mock_identity, mock_llm):
    bridge = TheBridge(mock_llm, mock_identity)
    payload = {"copy": "Let's talk about politics and the elections."}
    
    is_approved, reason = await bridge.evaluate(payload)
    
    assert not is_approved
    assert "Veto topic found: politics" in reason

@pytest.mark.asyncio
async def test_the_bridge_llm_semantic_veto(mock_identity, mock_llm):
    bridge = TheBridge(mock_llm, mock_identity)
    payload = {"copy": "This is totally normal copy."}
    
    # Mock the LLM returning a rejection JSON
    mock_llm.generate.return_value = '{"is_approved": false, "verdict_reason": "Manipulative urgency"}'
    
    is_approved, reason = await bridge.evaluate(payload)
    
    assert not is_approved
    assert reason == "Manipulative urgency"

@pytest.mark.asyncio
async def test_the_bridge_banned_words_substring_not_vetoed(mock_identity, mock_llm):
    bridge = TheBridge(mock_llm, mock_identity)
    # "guarantee" is banned, but "guarantees" should pass the word boundary check
    payload = {"copy": "We offer guarantees that you will see results."}
    
    mock_llm.generate.return_value = '{"is_approved": true, "verdict_reason": "Approved"}'
    is_approved, reason = await bridge.evaluate(payload)
    
    assert is_approved
    assert reason == "Approved"
