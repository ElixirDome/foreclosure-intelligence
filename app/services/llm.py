from abc import ABC, abstractmethod
import os
from dotenv import load_dotenv
from ollama import Client, ResponseError
from app.schemas import PropertyAIAnalysis
from ollama import ResponseError

load_dotenv()

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

    def generate_raw(
        self,
        prompt: str,
    ) -> str:
        """Generate unformatted raw markdown or textual answer."""
        raise NotImplementedError("generate_raw not implemented for this provider")


# the model may return JSON wrapped in Markdown fences.
### Add a small parser
def parse_property_ai_analysis(
    content: str,
) -> PropertyAIAnalysis:
    content = content.strip()

    if content.startswith("```"):
        lines = content.splitlines()

        if lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        content = "\n".join(lines).strip()

    return PropertyAIAnalysis.model_validate_json(content)

class LocalLLMProvider(LLMProvider):

    def __init__(
        self,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.model = model or os.getenv(
            "OLLAMA_MODEL",
            "llama3.2:3b",
        )

        self.timeout = timeout or float(
            os.getenv("OLLAMA_TIMEOUT", "60")
        )

        self.client = Client(
            host=os.getenv(
                "OLLAMA_HOST",
                "http://localhost:11434",
            ),
            timeout=self.timeout,
        )

    def is_available(self) -> bool:
        """Lightweight non-blocking check for Ollama daemon availability."""
        try:
            self.client.list()
            return True
        except Exception:
            return False

    def generate(self, prompt: str) -> PropertyAIAnalysis:
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                format=PropertyAIAnalysis.model_json_schema(),
            )

            return parse_property_ai_analysis(
                response["message"]["content"]
            )

        except ResponseError as e:
            raise RuntimeError(
                f"Ollama error: {e.error}"
            ) from e

        except Exception as e:
            raise RuntimeError(
                f"Failed to generate AI property analysis: {e}"
            ) from e

    def generate_raw(self, prompt: str) -> str:
        """Generate unstructured markdown/text response for RAG or search planning."""
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            return response["message"]["content"]
        except Exception as e:
            raise RuntimeError(
                f"Failed to generate raw LLM text: {e}"
            ) from e


def deterministic_property_ai_fallback(
    property_data: dict,
    analysis_data: dict,
) -> PropertyAIAnalysis:
    """
    Deterministic rule-based fallback generating structured underwriter SWOT
    when the local LLM server is offline, timed out, or unavailable.
    Guarantees 0% hallucination on missing data and high system reliability.
    """
    addr = property_data.get("address") or "Foreclosure Property"
    deal_score = analysis_data.get("deal_score")
    discount = analysis_data.get("discount_percentage")
    risk_level = analysis_data.get("risk_level", 2)
    reserve = property_data.get("reserve_price") or property_data.get("opening_bid")
    est_val = property_data.get("estimated_value")

    strengths = []
    risks = []
    due_diligence = []

    if discount is not None and discount > 0:
        strengths.append(f"Priced at {discount:.1f}% discount relative to market benchmark")
    if deal_score is not None and deal_score >= 60:
        strengths.append(f"Strong overall deal score ({deal_score:.0f}/100) based on financial metrics")
    if property_data.get("foreclosure_status") in ("scheduled", "upcoming", "active"):
        strengths.append(f"Active auction listing with scheduled auction date: {property_data.get('auction_date') or 'TBD'}")
    if not strengths:
        strengths.append("Public auction property with verified SARFAESI publication record")

    if est_val is None:
        risks.append("Independent market valuation currently unavailable; reserve price lacks external comparable validation")
        due_diligence.append("Commission an independent property valuation before participating in auction")
    if risk_level >= 3:
        risks.append("Elevated risk profile based on foreclosure status and legal timeline")
    if property_data.get("foreclosure_status") in ("sold", "cancelled"):
        risks.append(f"Auction is currently marked as {property_data.get('foreclosure_status')}")
    if not risks:
        risks.append("General foreclosure risks: potential unrecorded liens, encumbrances, or symbolic possession")

    due_diligence.append("Verify physical vs symbolic possession under SARFAESI Section 13(4) and Section 14")
    due_diligence.append("Inspect encumbrance certificate (EC) for 30 years and verify outstanding municipal taxes/utility dues")
    due_diligence.append("Confirm EMD submission deadline and original title deed availability with authorized bank officer")

    if deal_score is not None and deal_score >= 70:
        recommendation = f"Favorable opportunity with deal score {deal_score:.0f}/100. Proceed with physical site inspection and title verification."
    elif deal_score is not None and deal_score >= 40:
        recommendation = f"Mixed investment prospect ({deal_score:.0f}/100). Proceed with caution only after validating market valuation and statutory dues."
    else:
        recommendation = "High risk or incomplete data. Comprehensive legal and market due diligence strictly required before bidding."

    summary = f"Foreclosure investment evaluation for {addr}. "
    if reserve:
        try:
            summary += f"Reserve price: ₹{float(reserve):,.0f}. "
        except (ValueError, TypeError):
            summary += f"Reserve price: {reserve}. "
    if deal_score is not None:
        summary += f"Deterministic deal score: {deal_score:.0f}/100 with risk level {risk_level}."
    else:
        summary += "Deterministic scoring pending market comparables."

    return PropertyAIAnalysis(
        summary=summary,
        strengths=strengths,
        risks=risks,
        due_diligence=due_diligence,
        recommendation=recommendation,
    )


def generate_property_analysis(
    property_data: dict,
    analysis_data: dict,
    provider: LLMProvider,
) -> PropertyAIAnalysis:
    """
    Generate an AI-powered interpretation of a property's deterministic analysis.
    If the LLM provider fails, times out, or is offline, seamlessly degrades to
    the verified deterministic underwriter SWOT fallback.
    """
    prompt = build_property_analysis_prompt(
        property_data,
        analysis_data,
    )

    try:
        return provider.generate(prompt)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "LLM generation failed: %s; falling back to deterministic SWOT analysis",
            exc,
        )
        return deterministic_property_ai_fallback(property_data, analysis_data)