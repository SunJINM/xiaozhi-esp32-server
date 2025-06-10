from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict
from pydantic import BaseModel, ConfigDict, model_validator
from config.settings import load_config, check_config_file
from core.providers.llm.base import LLMProviderBase
from core.utils.dialogue import Message, Dialogue

class Agent(ABC, BaseModel):
    session_id: str
    llm: LLMProviderBase

    model_config = ConfigDict(
        extra='forbid',
        arbitrary_types_allowed=True
    )

    @model_validator(mode='before')
    def validate_environment(cls, values: Dict) -> Dict:
        if values["llm"] is None:
            raise ValueError("LLM必须初始化")
        return values


    @abstractmethod
    def _generate(self, dialogue: Dialogue):
        pass

    @abstractmethod
    def _suggest_generate(self, dialogue: Dialogue):
        pass


    def generate(self, dialogue: Dialogue):
        return self._generate(dialogue)
    

    def suggest_generate(self, dialogue: Dialogue):
        return self._suggest_generate(dialogue)

















