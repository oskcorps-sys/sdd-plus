from typing import Dict, Any
from .llm import LLMAdapter, OpenAIAdapter, AnthropicAdapter
from .channel import ChannelAdapter, TelegramAdapter

class AdapterFactory:
    @staticmethod
    def create_llm_adapter(config: Dict[str, Any]) -> LLMAdapter:
        provider = config.get("provider", "").lower()
        if provider == "openai":
            return OpenAIAdapter(
                api_key=config.get("api_key", ""),
                model=config.get("model", "gpt-4o")
            )
        elif provider == "anthropic":
            return AnthropicAdapter(
                api_key=config.get("api_key", ""),
                model=config.get("model", "claude-3-opus-20240229")
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @staticmethod
    def create_channel_adapter(config: Dict[str, Any]) -> ChannelAdapter:
        provider = config.get("provider", "").lower()
        if provider == "telegram":
            return TelegramAdapter(
                bot_token=config.get("bot_token", ""),
                chat_id=config.get("chat_id", "")
            )
        else:
            raise ValueError(f"Unknown channel provider: {provider}")
