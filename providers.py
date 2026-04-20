"""
Provider templates and configuration for LLM services.

Domestic (CN) and International (INT) providers with their API characteristics.

IMPORTANT: Model lists should be dynamically fetched via GET /models, not hardcoded.
Static fallback lists should only be used for providers that don't support /models (e.g., MiniMax).
"""
from __future__ import annotations

# Provider categories
CATEGORY_DOMESTIC = "Domestic"
CATEGORY_INTERNATIONAL = "International"
CATEGORY_AGGREGATOR = "Aggregator"
CATEGORY_CUSTOM = "Custom"

# Special model requirements
MODEL_SPECIAL_PARAMS = {
    "kimi-k2.5": {"temperature": 1, "max_tokens": 256},
    "kimi-k2-turbo-preview": {"temperature": 1, "max_tokens": 256},
    "kimi-k2-thinking-turbo": {"temperature": 1, "max_tokens": 256},
    "kimi-k2-thinking": {"temperature": 1, "max_tokens": 256},
}

# Reasoning/thinking models that may return empty content
REASONING_MODELS = [
    "deepseek-reasoner",
    "kimi-k2-thinking",
    "kimi-k2-thinking-turbo",
]

# Only providers that truly don't support /models need static lists
# Other providers' model lists should be fetched dynamically via API
STATIC_MODEL_FALLBACK = {
    "minimax": [  # MiniMax GET /models returns 404, must use static list
        "MiniMax-M2.7",
        "MiniMax-M2.7-highspeed",
        "MiniMax-M2.5",
        "MiniMax-M2.5-highspeed",
        "MiniMax-M2.1",
        "MiniMax-M2.1-highspeed",
        "MiniMax-M2",
        "M2-her",
    ],
}

PROVIDER_TEMPLATES = {
    # ==================== Aggregator Platforms ====================
    "aggregators_qiniu": {
        "name": "Qiniu AI",
        "name_cn": "Qiniu AI",
        "category": CATEGORY_AGGREGATOR,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.qnaigc.com",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "",
        "notes": "Supports Claude/Qwen/DeepSeek models; models fetched dynamically via /models",
    },
    "anyscale": {
        "name": "Anyscale",
        "name_cn": "Anyscale",
        "category": CATEGORY_AGGREGATOR,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.endpoints.anyscale.com/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "meta-llama/Llama-2-7b-chat-hf",
        "notes": "Open-source model aggregator; models fetched dynamically via /models",
    },
    "anthropic": {
        "name": "Anthropic",
        "name_cn": "Anthropic Claude",
        "category": CATEGORY_INTERNATIONAL,
        "adapter": "anthropic_messages",
        "base_url": "https://api.anthropic.com/v1",
        "supports_models_api": False,
        "static_fallback": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
        ],
        "default_model": "claude-3-5-sonnet-20241022",
        "notes": "Anthropic Claude series; uses dedicated adapter",
    },
    "baidu_qianfan": {
        "name": "Baidu Qianfan",
        "name_cn": "Baidu Qianfan",
        "category": CATEGORY_DOMESTIC,
        "adapter": "openai_chat_compatible",
        "base_url": "https://qianfan.baidubce.com/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "ernie-4.0-8k-latest",
        "notes": "Baidu Qianfan; models fetched dynamically via /models",
    },
    "cerebras": {
        "name": "Cerebras",
        "name_cn": "Cerebras",
        "category": CATEGORY_INTERNATIONAL,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.cerebras.ai/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "zai-glm-4.7",
        "notes": "High-speed inference; models fetched dynamically via /models",
    },
    "cohere": {
        "name": "Cohere",
        "name_cn": "Cohere",
        "category": CATEGORY_INTERNATIONAL,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.cohere.ai/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "command",
        "notes": "Chat endpoint is /chat (not /chat/completions); models via /models",
    },
    "custom_1": {
        "name": "CUSTOM_1",
        "name_cn": "CUSTOM_1",
        "category": CATEGORY_CUSTOM,
        "adapter": "openai_chat_compatible",
        "base_url": "",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "",
        "notes": "User-defined API endpoint",
    },
    "custom_2": {
        "name": "CUSTOM_2",
        "name_cn": "CUSTOM_2",
        "category": CATEGORY_CUSTOM,
        "adapter": "openai_chat_compatible",
        "base_url": "",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "",
        "notes": "User-defined API endpoint",
    },
    "custom_3": {
        "name": "CUSTOM_3",
        "name_cn": "CUSTOM_3",
        "category": CATEGORY_CUSTOM,
        "adapter": "openai_chat_compatible",
        "base_url": "",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "",
        "notes": "User-defined API endpoint",
    },
    "deepseek_cn": {
        "name": "DeepSeek CN",
        "name_cn": "DeepSeek CN",
        "category": CATEGORY_DOMESTIC,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.deepseek.com/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "deepseek-chat",
        "notes": "API key must be real, not a URL",
    },
    "deepseek_int": {
        "name": "DeepSeek Intl",
        "name_cn": "DeepSeek Intl",
        "category": CATEGORY_INTERNATIONAL,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.deepseek.com",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "deepseek-chat",
        "notes": "International DeepSeek endpoint",
    },
    "featherless": {
        "name": "Featherless AI",
        "name_cn": "Featherless AI",
        "category": CATEGORY_AGGREGATOR,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.featherless.ai/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "Qwen/Qwen2.5-7B-Instruct",
        "notes": "Open-source model aggregator; models fetched dynamically via /models",
    },
    "google_gemini": {
        "name": "Google Gemini",
        "name_cn": "Google Gemini",
        "category": CATEGORY_INTERNATIONAL,
        "adapter": "google_gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "gemini-1.5-flash",
        "notes": "Google Gemini series; models fetched dynamically via /models",
    },
    "groq": {
        "name": "Groq",
        "name_cn": "Groq",
        "category": CATEGORY_INTERNATIONAL,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "llama-3.1-70b-versatile",
        "notes": "High-speed inference; models fetched dynamically via /models",
    },
    "minimax": {
        "name": "MiniMax CN",
        "name_cn": "MiniMax CN",
        "category": CATEGORY_DOMESTIC,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.minimaxi.com/v1",
        "supports_models_api": False,
        "static_fallback": STATIC_MODEL_FALLBACK["minimax"],
        "default_model": "MiniMax-M2.7",
        "notes": "No /models endpoint; use static list or probe models individually",
    },
    "minimax_int": {
        "name": "MiniMax Intl",
        "name_cn": "MiniMax Intl",
        "category": CATEGORY_INTERNATIONAL,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.minimax.io/v1",
        "supports_models_api": False,
        "static_fallback": STATIC_MODEL_FALLBACK["minimax"],
        "default_model": "MiniMax-M2.7",
        "notes": "No /models endpoint; use static list or probe models individually",
    },
    "mistral_ai": {
        "name": "Mistral AI",
        "name_cn": "Mistral AI",
        "category": CATEGORY_INTERNATIONAL,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.mistral.ai/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "mistral-small-latest",
        "notes": "Models fetched dynamically via /models",
    },
    "moonshot_cn": {
        "name": "Moonshot CN",
        "name_cn": "Moonshot CN",
        "category": CATEGORY_DOMESTIC,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.moonshot.cn/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "moonshot-v1-32k",
        "notes": "kimi-k2.5 and similar models require temperature=1",
    },
    "n1n_ai": {
        "name": "n1n.ai",
        "name_cn": "n1n.ai",
        "category": CATEGORY_AGGREGATOR,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.n1n.ai/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "",
        "notes": "Domestic aggregator supporting Gemini/DeepSeek/OpenAI/Claude/Qwen; models fetched dynamically via /models",
    },
    "novita_ai": {
        "name": "Novita AI",
        "name_cn": "Novita AI",
        "category": CATEGORY_AGGREGATOR,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.novita.ai/openai",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "deepseek/deepseek-r1",
        "notes": "OpenAI-compatible endpoint; models fetched dynamically via /models",
    },
    "openai": {
        "name": "OpenAI",
        "name_cn": "OpenAI GPT",
        "category": CATEGORY_INTERNATIONAL,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.openai.com/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "gpt-4o",
        "notes": "OpenAI GPT series; models fetched dynamically via /models",
    },
    "openrouter": {
        "name": "OpenRouter",
        "name_cn": "OpenRouter",
        "category": CATEGORY_AGGREGATOR,
        "adapter": "openai_chat_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "anthropic/claude-3.5-sonnet",
        "notes": "International aggregator; models fetched dynamically via /models",
    },
    "qwen_aliyun": {
        "name": "Aliyun Qwen",
        "name_cn": "Aliyun Qwen",
        "category": CATEGORY_DOMESTIC,
        "adapter": "openai_chat_compatible",
        "base_url": "https://dashscope.aliyuncs.com/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "qwen-turbo",
        "notes": "Aliyun Bailian platform; models fetched dynamically via /models",
    },
    "siliconflow": {
        "name": "SiliconFlow",
        "name_cn": "SiliconFlow",
        "category": CATEGORY_AGGREGATOR,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.siliconflow.cn/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "deepseek-ai/DeepSeek-V3.2",
        "notes": "Aggregator platform; models fetched dynamically via /models",
    },
    "stepapi": {
        "name": "StepFun",
        "name_cn": "StepFun",
        "category": CATEGORY_DOMESTIC,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.stepfun.com/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "step-1v",
        "notes": "StepFun; models fetched dynamically via /models",
    },
    "togetherai": {
        "name": "Together.ai",
        "name_cn": "Together.ai",
        "category": CATEGORY_AGGREGATOR,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.together.ai/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "meta-llama/Llama-3-70b-chat-hf",
        "notes": "International aggregator; models fetched dynamically via /models",
    },
    "xi_api": {
        "name": "Xi-Api",
        "name_cn": "Xi-Api",
        "category": CATEGORY_AGGREGATOR,
        "adapter": "openai_chat_compatible",
        "base_url": "https://api.xi-ai.cn/v1",
        "supports_models_api": True,
        "static_fallback": [],
        "default_model": "",
        "notes": "Aggregator platform; models fetched dynamically via /models",
    },
    "zhipu": {
        "name": "Zhipu GLM",
        "name_cn": "Zhipu GLM",
        "category": CATEGORY_DOMESTIC,
        "adapter": "openai_chat_compatible",
        "base_url": "https://open.bigmodel.cn/v1",
        "supports_models_api": True,
        "static_fallback": [
            "glm-4",
            "glm-4-flash",
            "glm-4-plus",
            "glm-4v",
            "glm-3-turbo",
        ],
        "default_model": "glm-4",
        "notes": "Zhipu AI; models fetched dynamically via /models",
    },
}


def get_provider_template(provider_key: str):
    """Get provider template by key."""
    return PROVIDER_TEMPLATES.get(provider_key)


def list_providers():
    """List all available provider keys."""
    return list(PROVIDER_TEMPLATES.keys())


def list_providers_by_category():
    """List providers grouped by category."""
    categories = {}
    for key, template in PROVIDER_TEMPLATES.items():
        cat = template.get("category", CATEGORY_CUSTOM)
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(key)
    return categories


def get_provider_display_name(provider_key: str) -> str:
    """Get display name for a provider."""
    template = PROVIDER_TEMPLATES.get(provider_key)
    return template["name"] if template else provider_key


def get_provider_notes(provider_key: str) -> str:
    """Get provider notes."""
    template = PROVIDER_TEMPLATES.get(provider_key)
    return template.get("notes", "") if template else ""


def get_special_model_params(model_name: str) -> dict:
    """Get special parameters required for a model."""
    return MODEL_SPECIAL_PARAMS.get(model_name, {})


def is_reasoning_model(model_name: str) -> bool:
    """Check if model is a reasoning/thinking model."""
    # Use exact matching against known reasoning models
    model_lower = model_name.lower()
    return model_lower in [r.lower() for r in REASONING_MODELS]


def get_static_fallback_models(provider_key: str) -> list:
    """Get static fallback models for providers that don't support /models."""
    template = PROVIDER_TEMPLATES.get(provider_key)
    if template:
        return template.get("static_fallback", [])
    return []
