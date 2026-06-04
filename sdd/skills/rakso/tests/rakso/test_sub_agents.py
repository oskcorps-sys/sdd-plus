import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from src.rakso.agents.sub_agents import RAKSOCreativo, NeurofunnelSub, ModuleC
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

@pytest.mark.asyncio
async def test_rakso_creativo_execute(mock_identity, mock_llm):
    mock_llm.generate.return_value = " This is creative copy. "
    agent = RAKSOCreativo(mock_llm, mock_identity)
    
    result = await agent.execute({"brief": "test"})
    assert result == {"copy": "This is creative copy."}

@pytest.mark.asyncio
async def test_neurofunnel_sub_execute(mock_identity, mock_llm):
    mock_llm.generate.return_value = " AWARENESS "
    agent = NeurofunnelSub(mock_llm, mock_identity)
    
    result = await agent.execute({"brief": "test"})
    assert result == {"funnel_stage": "AWARENESS"}

@pytest.mark.asyncio
async def test_module_c_execute_valid_json(mock_identity, mock_llm):
    mock_llm.generate.return_value = '```json\n{"core_emotion": "joy", "cognitive_bias": "halo effect"}\n```'
    agent = ModuleC(mock_llm, mock_identity)
    
    result = await agent.execute({"brief": "test"})
    assert result == {"core_emotion": "joy", "cognitive_bias": "halo effect"}

@pytest.mark.asyncio
async def test_module_c_execute_invalid_json(mock_identity, mock_llm):
    mock_llm.generate.return_value = 'Not a JSON'
    agent = ModuleC(mock_llm, mock_identity)
    
    result = await agent.execute({"brief": "test"})
    assert result == {"core_emotion": "unknown", "cognitive_bias": "unknown"}

@pytest.mark.asyncio
async def test_module_c_execute_non_dict_json(mock_identity, mock_llm):
    mock_llm.generate.return_value = '["not", "a", "dict"]'
    agent = ModuleC(mock_llm, mock_identity)
    
    result = await agent.execute({"brief": "test"})
    assert result == {"result": ["not", "a", "dict"]}

