from app.services.llm import LocalLLMProvider

def get_llm_provider() -> LocalLLMProvider:
    return LocalLLMProvider()