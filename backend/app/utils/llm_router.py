from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from app.config import get_settings

settings = get_settings()

_TIER_CONFIGS = {
    # (tier, provider) -> (model, model_provider, api_key_attr, base_url|None, extra_kwargs)
    ("fast", "openai"):     ("gpt-4o-mini",                  "openai",       "OPENAI_API_KEY",    None, None),
    ("fast", "deepseek"):   ("deepseek-chat",                "openai",       "DEEPSEEK_API_KEY",  "https://api.deepseek.com/v1", None),
    ("fast", "gemini"):     ("gemini-2.0-flash",             "google-genai", "GEMINI_API_KEY",    None, None),
    ("fast", "aliyun"):     ("qwen-plus",                    "openai",       "ALIYUN_API_KEY",    "https://dashscope.aliyuncs.com/compatible-mode/v1", None),
    ("fast", "openrouter"): ("qwen/qwen3-4b:free",          "openai",       "OPENROUTER_API_KEY","https://openrouter.ai/api/v1", {"extra_headers": {"HTTP-Referer": "https://treeedu.ai", "X-Title": "TreeEdu Agent"}}),
    ("fast", "minimax"):    ("MiniMax-M2.5",                 "anthropic",    "MINIMAX_API_KEY",   "https://api.minimaxi.com/anthropic", None),

    ("medium", "openai"):     ("gpt-4o-mini",               "openai",       "OPENAI_API_KEY",    None, None),
    ("medium", "deepseek"):   ("deepseek-chat",             "openai",       "DEEPSEEK_API_KEY",  "https://api.deepseek.com/v1", None),
    ("medium", "gemini"):     ("gemini-2.0-flash",          "google-genai", "GEMINI_API_KEY",    None, None),
    ("medium", "aliyun"):     ("qwen/qwen3-4b",             "openai",       "ALIYUN_API_KEY",    "https://dashscope.aliyuncs.com/compatible-mode/v1", None),
    ("medium", "openrouter"): ("google/gemma-3-27b-it:free","openai",       "OPENROUTER_API_KEY","https://openrouter.ai/api/v1", {"extra_headers": {"HTTP-Referer": "https://treeedu.ai", "X-Title": "TreeEdu Agent"}}),
    ("medium", "minimax"):    ("MiniMax-M2.5",              "anthropic",    "MINIMAX_API_KEY",   "https://api.minimaxi.com/anthropic", None),

    ("heavy", "openai"):     ("gpt-4o",                     "openai",       "OPENAI_API_KEY",    None, None),
    ("heavy", "deepseek"):   ("deepseek-chat",              "openai",       "DEEPSEEK_API_KEY",  "https://api.deepseek.com/v1", None),
    ("heavy", "gemini"):     ("gemini-2.5-pro",             "google-genai", "GEMINI_API_KEY",    None, None),
    ("heavy", "aliyun"):     ("qwen-max-latest",            "openai",       "ALIYUN_API_KEY",    "https://dashscope.aliyuncs.com/compatible-mode/v1", None),
    ("heavy", "openrouter"): ("stepfun/step-3.5-flash:free","openai",       "OPENROUTER_API_KEY","https://openrouter.ai/api/v1", {"extra_headers": {"HTTP-Referer": "https://treeedu.ai", "X-Title": "TreeEdu Agent"}}),
    ("heavy", "minimax"):    ("MiniMax-M2.7",               "anthropic",    "MINIMAX_API_KEY",   "https://api.minimaxi.com/anthropic", None),

    ("vision", "openai"):     ("gpt-4o",                    "openai",       "OPENAI_API_KEY",    None, None),
    ("vision", "aliyun"):     ("qwen-vl-max-latest",        "openai",       "ALIYUN_API_KEY",    "https://dashscope.aliyuncs.com/compatible-mode/v1", None),
    ("vision", "openrouter"): ("nvidia/nemotron-nano-12b-v2-vl:free","openai","OPENROUTER_API_KEY","https://openrouter.ai/api/v1", {"extra_headers": {"HTTP-Referer": "https://treeedu.ai", "X-Title": "TreeEdu Agent"}}),
    ("vision", "minimax"):    ("MiniMax-M2.7",              "openai",       "MINIMAX_API_KEY",   "https://api.minimaxi.com/anthropic/v1", None),
}

_TIMEOUT = {"fast": 60.0, "medium": 120.0, "heavy": 180.0, "vision": 120.0}

_TIER_SETTING_KEY = {
    "fast": "LLM_FAST_MODEL",
    "medium": "LLM_MEDIUM_MODEL",
    "heavy": "LLM_HEAVY_MODEL",
    "vision": "LLM_VISION_MODEL",
}


def _build_model(tier: str, temperature: float) -> BaseChatModel:
    provider = getattr(settings, _TIER_SETTING_KEY[tier]).lower().strip()
    key = (tier, provider)
    if key not in _TIER_CONFIGS:
        raise ValueError(f"Unknown config: tier={tier}, provider={provider}")

    model, model_provider, api_key_attr, base_url, extra = _TIER_CONFIGS[key]
    kwargs = {
        "model": model,
        "model_provider": model_provider,
        "api_key": getattr(settings, api_key_attr),
        "temperature": temperature,
        "timeout": _TIMEOUT[tier],
        "max_retries": 3,
    }
    if base_url:
        kwargs["base_url"] = base_url
    if extra:
        kwargs.update(extra)

    return init_chat_model(**kwargs)


@lru_cache(maxsize=16)
def get_fast_model(temperature: float = 0.0) -> BaseChatModel:
    return _build_model("fast", temperature)


@lru_cache(maxsize=16)
def get_medium_model(temperature: float = 0.3) -> BaseChatModel:
    return _build_model("medium", temperature)


@lru_cache(maxsize=16)
def get_heavy_model(temperature: float = 0.2) -> BaseChatModel:
    return _build_model("heavy", temperature)


@lru_cache(maxsize=4)
def get_vision_model(temperature: float = 0.0) -> BaseChatModel:
    return _build_model("vision", temperature)
