import pytest
from unittest.mock import patch, MagicMock
import httpx
from src.rakso.adapters.factory import AdapterFactory

@pytest.mark.asyncio
async def test_model_adapter_swappability_happy_path():
    """Happy path: Create different adapters via config and run generate/publish."""
    # OpenAI
    config_openai = {"provider": "openai", "api_key": "test_key", "model": "gpt-4o"}
    adapter_openai = AdapterFactory.create_llm_adapter(config_openai)
    
    with patch("src.rakso.adapters.llm.httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "OpenAI Response"}}]}
        mock_post.return_value = mock_response
        
        result_openai = await adapter_openai.generate("Hello")
        assert result_openai == "OpenAI Response"
        
    # Anthropic
    config_anthropic = {"provider": "anthropic", "api_key": "test_key", "model": "claude-3"}
    adapter_anthropic = AdapterFactory.create_llm_adapter(config_anthropic)
    
    with patch("src.rakso.adapters.llm.httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "Anthropic Response"}]}
        mock_post.return_value = mock_response
        
        result_anthropic = await adapter_anthropic.generate("Hello")
        assert result_anthropic == "Anthropic Response"
        
    # Telegram
    config_telegram = {"provider": "telegram", "bot_token": "token", "chat_id": "123"}
    adapter_telegram = AdapterFactory.create_channel_adapter(config_telegram)
    
    with patch("src.rakso.adapters.channel.httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response
        
        result_tg = await adapter_telegram.publish({"copy": "Test"})
        assert result_tg is True

@pytest.mark.asyncio
async def test_model_adapter_swappability_edge_case():
    """Edge case: unknown configs."""
    # Unknowns
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        AdapterFactory.create_llm_adapter({"provider": "invalid"})
        
    with pytest.raises(ValueError, match="Unknown channel provider"):
        AdapterFactory.create_channel_adapter({"provider": "invalid"})

@pytest.mark.asyncio
async def test_model_adapter_swappability_error_handling():
    """Error handling: HTTP errors during API calls raise exceptions."""
    config_openai = {"provider": "openai", "api_key": "test_key"}
    adapter_openai = AdapterFactory.create_llm_adapter(config_openai)
    
    with patch("src.rakso.adapters.llm.httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            message="Unauthorized",
            request=httpx.Request("POST", "https://api.openai.com"),
            response=httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com"))
        )
        with pytest.raises(httpx.HTTPStatusError):
            await adapter_openai.generate("Hello")
            
    config_tg = {"provider": "telegram", "bot_token": "t", "chat_id": "1"}
    adapter_tg = AdapterFactory.create_channel_adapter(config_tg)
    with patch("src.rakso.adapters.channel.httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            message="Not Found",
            request=httpx.Request("POST", "tg"),
            response=httpx.Response(404, request=httpx.Request("POST", "tg"))
        )
        with pytest.raises(httpx.HTTPStatusError):
            await adapter_tg.publish({"copy": "Hi"})
