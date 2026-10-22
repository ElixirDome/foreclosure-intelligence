from app.services.llm import build_property_analysis_prompt, LocalLLMProvider, generate_property_analysis,parse_property_ai_analysis
import ollama
from app.schemas import PropertyAIAnalysis

def test_build_property_analysis_prompt():
    property_data = {
        "address": "123 Main Street",
        "property_type": "single_family",
        "price": 100000,
        "bedrooms": 3,
        "bathrooms": 2,
        "area_sqft": 1500,
        "auction_date": "2026-08-22",
        "foreclosure_status": "active",
        "opening_bid": 60000,
        "estimated_value": 90000,
    }

    analysis_data = {
        "discount_percentage": 33.33,
        "risk_level": 2,
        "deal_score": 23.33,
    }

    prompt = build_property_analysis_prompt(
        property_data,
        analysis_data,
    )

    assert "123 Main Street" in prompt
    assert "90000" in prompt
    assert "60000" in prompt
    assert "33.33" in prompt
    assert "23.33" in prompt

def test_local_llm_provider_initializes():
    provider = LocalLLMProvider()

    assert provider.model == "llama3.2:3b"

def test_local_llm_provider_generates_analysis(monkeypatch):
    class FakeOllamaClient:
        def __init__(self, host, timeout):
            self.host = host
            self.timeout = timeout

        def chat(self, **kwargs):
            return {
                "message": {
                    "content": """{
                        "summary": "Test summary",
                        "strengths": ["Test strength"],
                        "risks": ["Test risk"],
                        "due_diligence": ["Verify title"],
                        "recommendation": "Investigate further."
                    }"""
                }
            }

    monkeypatch.setattr("app.services.llm.Client", FakeOllamaClient)
    provider = LocalLLMProvider()
    result = provider.generate("test prompt")

    assert isinstance(result, PropertyAIAnalysis)
    assert result.summary == "Test summary"
    assert result.strengths == ["Test strength"]
    assert result.risks == ["Test risk"]
    assert result.due_diligence == ["Verify title"]
    assert result.recommendation == "Investigate further."

def test_generate_property_analysis_with_fake_provider(fake_llm_provider):
    property_data = {
        "address": "123 Main Street",
        "estimated_value": 90000,
        "opening_bid": 60000,
    }

    analysis_data = {
        "discount_percentage": 33.33,
        "risk_level": 2,
        "deal_score": 23.33,
    }

    result = generate_property_analysis(
        property_data=property_data,
        analysis_data=analysis_data,
        provider=fake_llm_provider,
    )

    assert isinstance(result, PropertyAIAnalysis)
    assert result.summary == "Test property analysis."

def test_parse_property_ai_analysis_with_markdown_json():
    content = """```json
{
    "summary": "Good opportunity",
    "strengths": ["Strong discount"],
    "risks": ["Foreclosure risk"],
    "due_diligence": ["Verify title"],
    "recommendation": "Investigate further."
}
```"""

    result = parse_property_ai_analysis(content)

    assert isinstance(result, PropertyAIAnalysis)
    assert result.summary == "Good opportunity"
    assert result.recommendation == "Investigate further."
   