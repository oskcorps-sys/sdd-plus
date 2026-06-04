import pytest
from unittest.mock import AsyncMock, MagicMock
from src.rakso.orchestration.bridge import TheBridge
from src.rakso.identity.models import IdentityPack, VoiceConfig, VisualConfig, ProductConfig, HardLimitsConfig
from src.rakso.adapters.llm import LLMAdapter

@pytest.fixture
def mock_identity():
    return IdentityPack(
        voice=VoiceConfig(tone="professional", vocabulary=["innovative"]),
        visual=VisualConfig(color_palette=["#000"], style="minimalist"),
        product=ProductConfig(name="RAKSO", description="OS", target_audience=["marketers"]),
        hard_limits=HardLimitsConfig(banned_words=["miracle"], veto_topics=["politics"])
    )

@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=LLMAdapter)
    llm.generate = AsyncMock()
    return llm

@pytest.mark.asyncio
async def test_the_bridge_llm_semantic_fallback_veto(mock_identity, mock_llm):
    bridge = TheBridge(mock_llm, mock_identity)
    payload = {"copy": "This is totally normal copy."}
    
    mock_llm.generate.return_value = 'The copy is not approved because it is manipulative.'
    
    is_approved, reason = await bridge.evaluate(payload)
    
    assert not is_approved
    assert reason == "Fail-closed due to exception or invalid format"

@pytest.mark.asyncio
async def test_the_bridge_llm_semantic_fallback_approval(mock_identity, mock_llm):
    bridge = TheBridge(mock_llm, mock_identity)
    payload = {"copy": "This is totally normal copy."}
    
    mock_llm.generate.return_value = 'The copy looks fine to me.'
    
    is_approved, reason = await bridge.evaluate(payload)
    
    # Should fail-closed if JSON is invalid
    assert not is_approved
    assert reason == "Fail-closed due to exception or invalid format"
