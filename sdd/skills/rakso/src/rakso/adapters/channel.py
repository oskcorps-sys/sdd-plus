from abc import ABC, abstractmethod
from typing import Any, Dict
import httpx

class ChannelAdapter(ABC):
    """Base interface for all publishing channels."""
    
    @abstractmethod
    async def publish(self, payload: Dict[str, Any]) -> bool:
        """Publish payload to the channel."""
        pass

class TelegramAdapter(ChannelAdapter):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
    async def publish(self, payload: Dict[str, Any]) -> bool:
        message = payload.get("copy", str(payload))
        data = {
            "chat_id": self.chat_id,
            "text": message
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, json=data)
            response.raise_for_status()
            return response.json().get("ok", False)
