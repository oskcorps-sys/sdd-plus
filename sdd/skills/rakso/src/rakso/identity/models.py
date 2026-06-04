from pydantic import BaseModel, Field
from typing import List

class VoiceConfig(BaseModel):
    tone: str
    vocabulary: List[str] = Field(default_factory=list)

class VisualConfig(BaseModel):
    color_palette: List[str] = Field(default_factory=list)
    style: str

class ProductConfig(BaseModel):
    name: str
    description: str
    target_audience: List[str] = Field(default_factory=list)

class HardLimitsConfig(BaseModel):
    banned_words: List[str] = Field(default_factory=list)
    veto_topics: List[str] = Field(default_factory=list)

class IdentityPack(BaseModel):
    voice: VoiceConfig
    visual: VisualConfig
    product: ProductConfig
    hard_limits: HardLimitsConfig
