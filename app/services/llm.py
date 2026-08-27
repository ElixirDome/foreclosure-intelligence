from abc import ABC, abstractmethod

import ollama

from app.schemas import PropertyAIAnalysis


def build_property_analysis_prompt(
    property_data: dict,
    analysis_data: dict,
) -> str:
    """
    Build the prompt used to generate an AI-powered
    interpretation of a property's deterministic analysis.
    """

    instructions = """
You are a foreclosure investment analysis assistant.

Analyze the property using only the information provided
in the property data and deterministic analysis.

Do not invent facts, values, comparable properties,
financial figures, or legal conclusions.

If important information is missing, explicitly say so.

Your analysis should help an investor understand the
potential opportunity, risks, and recommended due diligence.

The response must provide all of these fields:

- summary: a concise overall interpretation
- strengths: important positive factors
- risks: important risks or uncertainties
- due_diligence: specific checks an investor should perform
- recommendation: a clear investment-oriented recommendation based only on the supplied data

Every field must contain meaningful content.
Do not leave any field empty.
"""

    property_context = f"""
PROPERTY DATA

Address: {property_data.get("address")}
Property type: {property_data.get("property_type")}
Price: {property_data.get("price")}
Bedrooms: {property_data.get("bedrooms")}
Bathrooms: {property_data.get("bathrooms")}
Area (sqft): {property_data.get("area_sqft")}
Auction date: {property_data.get("auction_date")}
Foreclosure status: {property_data.get("foreclosure_status")}
Opening bid: {property_data.get("opening_bid")}
Estimated value: {property_data.get("estimated_value")}
"""

    analysis_context = f"""
DETERMINISTIC ANALYSIS

Discount percentage: {analysis_data.get("discount_percentage")}
Risk level: {analysis_data.get("risk_level")}
Deal score: {analysis_data.get("deal_score")}
"""

    return f"""
{instructions}

{property_context}

{analysis_context}
"""


class LLMProvider(ABC):

    @abstractmethod
    def generate(
        self,
        prompt: str,
    ) -> PropertyAIAnalysis:
        pass


class LocalLLMProvider(LLMProvider):

    def __init__(self, model: str = "llama3.2:3b"):
        self.model = model

    def generate(self, prompt: str) -> PropertyAIAnalysis:
        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format=PropertyAIAnalysis.model_json_schema(),#We're giving Ollama the schema describing the structure we expect.
        )

        return PropertyAIAnalysis.model_validate_json(
            response["message"]["content"]
        )


def generate_property_analysis(
    property_data: dict,
    analysis_data: dict,
    provider: LLMProvider,
) -> PropertyAIAnalysis:
    """
    Generate an AI-powered interpretation of a property's
    deterministic analysis.
    """

    prompt = build_property_analysis_prompt(
        property_data,
        analysis_data,
    )

    return provider.generate(prompt)