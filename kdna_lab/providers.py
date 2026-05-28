"""KDNA Lab — Multi-Provider LLM Adapters.

Provides a unified interface for calling different LLM providers:
  - OpenAI (gpt-4o, gpt-4.1, etc.)
  - OpenAI-compatible (DeepSeek, Kimi, Groq, local vLLM, etc.)
  - Anthropic (Claude Sonnet, Claude Opus)

All adapters return Optional[str] — the response text or None on failure.
The ExperimentRunner uses these adapters via its call_api() method.
"""

import os
from typing import Any, Dict, Optional


class ProviderAdapter:
    """Base class for LLM provider adapters."""

    provider_name: str = "base"

    def call(
        self,
        prompt: str,
        model: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        **kwargs,
    ) -> Optional[str]:
        raise NotImplementedError


# ---- OpenAI Adapter ----

class OpenAIAdapter(ProviderAdapter):
    """OpenAI native API adapter."""

    provider_name = "openai"

    def call(self, prompt, model="gpt-4o", system_prompt="",
             temperature=0.3, max_tokens=4000, api_key=None, base_url=None, **kwargs):
        try:
            from openai import OpenAI
        except ImportError:
            return None

        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            return None

        client = OpenAI(api_key=key, base_url=base_url) if base_url else OpenAI(api_key=key)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception:
            return None


# ---- Anthropic Adapter ----

class AnthropicAdapter(ProviderAdapter):
    """Anthropic Claude API adapter."""

    provider_name = "anthropic"

    def call(self, prompt, model="claude-sonnet-4-20250514", system_prompt="",
             temperature=0.3, max_tokens=4000, api_key=None, **kwargs):
        try:
            import anthropic
        except ImportError:
            return None

        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return None

        client = anthropic.Anthropic(api_key=key)

        try:
            if system_prompt:
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
            else:
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
            return response.content[0].text if response.content else None
        except Exception:
            return None


# ---- OpenAI-Compatible Adapter (DeepSeek / Kimi / vLLM etc.) ----

class OpenAICompatibleAdapter(ProviderAdapter):
    """Adapter for any OpenAI-compatible API (DeepSeek, Kimi, Groq, local models).

    Configure with base_url pointing to the provider's endpoint.
    Uses OPENAI_API_KEY (or a provider-specific env var) for authentication.
    """

    provider_name = "openai_compatible"

    def call(self, prompt, model="gpt-4o", system_prompt="",
             temperature=0.3, max_tokens=4000, api_key=None,
             base_url=None, **kwargs):
        try:
            from openai import OpenAI
        except ImportError:
            return None

        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            return None

        client = OpenAI(api_key=key, base_url=base_url)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception:
            return None


# ---- Provider Registry ----

PROVIDERS: Dict[str, ProviderAdapter] = {
    "openai": OpenAIAdapter(),
    "anthropic": AnthropicAdapter(),
    "openai_compatible": OpenAICompatibleAdapter(),
}

# Provider presets for popular models
PROVIDER_PRESETS = {
    # OpenAI
    "gpt-4o": {"provider": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"},
    "gpt-4.1": {"provider": "openai", "model": "gpt-4.1", "api_key_env": "OPENAI_API_KEY"},
    # Anthropic
    "claude-sonnet-4-20250514": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "api_key_env": "ANTHROPIC_API_KEY"},
    "claude-opus-4-20250514": {"provider": "anthropic", "model": "claude-opus-4-20250514", "api_key_env": "ANTHROPIC_API_KEY"},
    # DeepSeek
    "deepseek-chat": {"provider": "openai_compatible", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1", "api_key_env": "DEEPSEEK_API_KEY"},
    "deepseek-reasoner": {"provider": "openai_compatible", "model": "deepseek-reasoner", "base_url": "https://api.deepseek.com/v1", "api_key_env": "DEEPSEEK_API_KEY"},
    # Kimi (Moonshot)
    "kimi-k2": {"provider": "openai_compatible", "model": "kimi-k2", "base_url": "https://api.moonshot.cn/v1", "api_key_env": "MOONSHOT_API_KEY"},
    # OpenCode Go models (via OpenAI-compatible API)
    "opencode-deepseek-v4-pro": {"provider": "openai_compatible", "model": "deepseek-v4-pro", "base_url": "https://api.opencode.ai/v1", "api_key_env": "OPENCODE_GO_API_KEY"},
    "opencode-deepseek-v4-flash": {"provider": "openai_compatible", "model": "deepseek-v4-flash", "base_url": "https://api.opencode.ai/v1", "api_key_env": "OPENCODE_GO_API_KEY"},
    "opencode-kimi-k2.6": {"provider": "openai_compatible", "model": "kimi-k2.6", "base_url": "https://api.opencode.ai/v1", "api_key_env": "OPENCODE_GO_API_KEY"},
    "opencode-qwen3.6-plus": {"provider": "openai_compatible", "model": "qwen3.6-plus", "base_url": "https://api.opencode.ai/v1", "api_key_env": "OPENCODE_GO_API_KEY"},
    "opencode-minimax-m2.7": {"provider": "openai_compatible", "model": "minimax-m2.7", "base_url": "https://api.opencode.ai/v1", "api_key_env": "OPENCODE_GO_API_KEY"},
    "opencode-glm-5.1": {"provider": "openai_compatible", "model": "glm-5.1", "base_url": "https://api.opencode.ai/v1", "api_key_env": "OPENCODE_GO_API_KEY"},
}


def get_provider(name: str) -> Optional[ProviderAdapter]:
    """Get a provider adapter by name."""
    return PROVIDERS.get(name)


def call_provider(
    provider_name: str,
    prompt: str,
    model: str,
    system_prompt: str = "",
    temperature: float = 0.3,
    max_tokens: int = 4000,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[str]:
    """Convenience function: call a provider by name.

    Returns response text or None on failure.
    """
    adapter = get_provider(provider_name)
    if adapter is None:
        return None
    return adapter.call(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        base_url=base_url,
    )
