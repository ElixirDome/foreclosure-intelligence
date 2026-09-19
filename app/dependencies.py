from app.services.llm import LocalLLMProvider, LLMProvider

def get_llm_provider() -> LocalLLMProvider:
    return LocalLLMProvider()