from langchain_core.language_models.chat_models import BaseChatModel
from app.config import get_settings

settings = get_settings()

def _get_model(provider_name: str, temperature: float = 0.0) -> BaseChatModel:
    """Helper to instantiate the correct LangChain chat model based on provider string."""
    provider = provider_name.lower().strip()
    
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY, 
            model="gpt-4o-mini", # default to mini unless heavy is requested below
            temperature=temperature
        )
    elif provider == "deepseek":
        from langchain_openai import ChatOpenAI
        # DeepSeek is usually OpenAI-compatible
        return ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            temperature=temperature
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            google_api_key=settings.GEMINI_API_KEY,
            model="gemini-2.0-flash", 
            temperature=temperature
        )
    elif provider == "aliyun":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.ALIYUN_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-max-latest", # Recommended default
            temperature=temperature
        )
    else:
        raise ValueError(f"Unknown LLM provider configured: {provider}")

def get_fast_model(temperature: float = 0.0) -> BaseChatModel:
    """Returns the LLM for fast, cheap tasks like intent routing or planning."""
    return _get_model(settings.LLM_FAST_MODEL, temperature=temperature)

def get_heavy_model(temperature: float = 0.2) -> BaseChatModel:
    """Returns the LLM for deep reasoning, Socratic questioning, and assessment."""
    provider = settings.LLM_HEAVY_MODEL.lower().strip()
    
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY, 
            model="gpt-4o", # overriding to heavy model
            temperature=temperature
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            google_api_key=settings.GEMINI_API_KEY,
            model="gemini-2.5-pro",
            temperature=temperature
        )
    elif provider == "aliyun":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.ALIYUN_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-max-latest",
            temperature=temperature
        )
    # DeepSeek handled generally in _get_model if "deepseek-reasoner" is desired we can branch here
    return _get_model(provider, temperature=temperature)

def get_vision_model(temperature: float = 0.0) -> BaseChatModel:
    """Returns the LLM capable of Vision OCR."""
    provider = settings.LLM_VISION_MODEL.lower().strip()
    
    if provider == "aliyun":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.ALIYUN_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-vl-max-latest",
            temperature=temperature,
            timeout=120.0,
            max_retries=3
        )
        
    # Often just the fast or heavy model that supports vision (e.g., gpt-4o, gemini-1.5-flash)
    return _get_model(provider, temperature=temperature)
