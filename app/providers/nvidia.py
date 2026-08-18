"""NVIDIA Nemotron LLM provider.

Wraps ChatNVIDIA for use in the intelligence layer.
"""

from __future__ import annotations

import warnings
from typing import Any

from app import config


class NvidiaProvider:
    """Thin wrapper around ChatNVIDIA for Nemotron reasoning."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "nvidia/nemotron-3-ultra-550b-a55b",
        temperature: float = 1.0,
        top_p: float = 0.95,
        max_tokens: int = 16384,
        reasoning_budget: int = 16384,
    ):
        self._api_key = api_key or config.NVIDIA_API_KEY
        self._model = model
        self._temperature = temperature
        self._top_p = top_p
        self._max_tokens = max_tokens
        self._reasoning_budget = reasoning_budget
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA

            self._client = ChatNVIDIA(
                model=self._model,
                api_key=self._api_key,
                temperature=self._temperature,
                top_p=self._top_p,
                max_tokens=self._max_tokens,
                model_kwargs={
                    "reasoning_budget": self._reasoning_budget,
                    "chat_template_kwargs": {"enable_thinking": True},
                },
            )
        return self._client

    def invoke(self, messages: list[dict[str, str]]) -> str:
        """Send messages and return the full text response.

        Messages should be in OpenAI format:
            [{"role": "user", "content": "..."}]
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = self.client.invoke(messages)
        return response.content

    def invoke_with_reasoning(self, messages: list[dict[str, str]]) -> dict[str, str]:
        """Send messages and return both reasoning and content."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = self.client.invoke(messages)
        reasoning = ""
        if hasattr(response, "additional_kwargs"):
            reasoning = response.additional_kwargs.get("reasoning_content", "")
        return {"reasoning": reasoning, "content": response.content}
