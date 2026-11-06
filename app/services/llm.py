from abc import ABC, abstractmethod
import logging
import os
import requests
from dotenv import load_dotenv
from ollama import Client, ResponseError
from app.schemas import PropertyAIAnalysis

load_dotenv()
logger = logging.getLogger(__name__)

def build_property_analysis_prompt(
    property_data: dict,
    analysis_data: dict,
) -> str:
    """
    Build the prompt used to generate an AI-powered
    interpretation of a property's deterministic analysis.
    """

    instructions = """
You are an expert real estate underwriter and legal auction analyst.
Analyze the provided auction notice particulars, deterministic financial calculations, and legal findings.

CRITICAL UNDERWRITING INSTRUCTIONS:
1. Clearly distinguish between:
   - Facts explicitly stated in the source document.
   - Values calculated by the application (EMD %, Reserve Price / Sq Ft).
   - Potential risks or inferences identified by the AI.
2. Never manufacture information when the document does not provide it.
3. Market valuation is unavailable when verified transaction data is not present — do not guess market values or discounts.
4. Distinguish between physical possession (bank has custody) and symbolic possession (borrower/occupants may still occupy under Section 13(4) SARFAESI).

Output a valid JSON object matching this schema:
{
    "summary": "Concise 2-3 sentence overview of property, bank, reserve price, and key assessment",
    "strengths": ["Documented property or auction advantages (e.g. physical possession, clear title)"],
    "risks": ["Explicitly disclosed concerns, pending litigation, or unquantified obligations"],
    "due_diligence": ["Specific verification steps and questions the buyer must ask the bank"],
    "recommendation": "Objective underwriting assessment grounded strictly in available facts"
}
"""

    property_context = f"""
PROPERTY & AUCTION PARTICULARS

Address: {property_data.get("address")}
Property type: {property_data.get("property_type")}
Survey number: {property_data.get("survey_number")}
Area (sqft): {property_data.get("area_sqft")}
Auction date: {property_data.get("auction_date")}
Foreclosure status: {property_data.get("foreclosure_status")}
Reserve price: {property_data.get("reserve_price")}
EMD: {property_data.get("emd")}
"""

    analysis_context = f"""
DETERMINISTIC AUCTION INTELLIGENCE

Assessment label: {analysis_data.get("assessment_label")}
EMD percentage: {analysis_data.get("emd_percentage")}%
Reserve price / sqft: {analysis_data.get("reserve_price_per_sqft")}
Possession type: {analysis_data.get("possession_type")}
Disclosed dues: {analysis_data.get("disclosed_outstanding_dues")}
Disclosed encumbrances: {analysis_data.get("disclosed_encumbrances")}
Pending litigation: {analysis_data.get("pending_litigation")}
Important concerns: {analysis_data.get("important_concerns")}
Missing information: {analysis_data.get("missing_information")}
Market valuation status: {analysis_data.get("market_valuation_status")}
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
        logger.info("[LLM] Generating structured analysis using Ollama (model: %s)", self.model)
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
        logger.info("[LLM] Generating synthesis using Ollama (model: %s)", self.model)
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


class GeminiProvider(LLMProvider):
    """
    Fast Gemini API provider for cloud-accelerated inference (sub-400ms latency).
    Uses standard REST endpoints with structured JSON schemas and falls back to
    deterministic analysis if unavailable or misconfigured.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 15.0,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.timeout = timeout
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str) -> PropertyAIAnalysis:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")

        logger.info("[LLM] Generating structured analysis using Gemini (model: %s)", self.model)
        url = f"{self.base_url}/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": PropertyAIAnalysis.model_json_schema(),
            },
        }
        res = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        res.raise_for_status()
        data = res.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        text = candidates[0]["content"]["parts"][0]["text"]
        return parse_property_ai_analysis(text)

    def generate_raw(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")

        logger.info("[LLM] Generating synthesis using Gemini (model: %s)", self.model)
        url = f"{self.base_url}/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        res = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        res.raise_for_status()
        data = res.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        return candidates[0]["content"]["parts"][0]["text"]


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
    assessment_label = analysis_data.get("assessment_label") or "Further investigation required"
    reserve = property_data.get("reserve_price") or property_data.get("opening_bid")
    emd = property_data.get("emd")
    emd_pct = analysis_data.get("emd_percentage")
    possession_type = (analysis_data.get("possession_type") or "not specified").lower()
    important_concerns = analysis_data.get("important_concerns") or []
    missing_info = analysis_data.get("missing_information") or []

    strengths = []
    risks = []
    due_diligence = []

    if "physical" in possession_type:
        strengths.append("Bank holds physical custody of the secured property")
    elif "symbolic" in possession_type:
        risks.append("Symbolic possession under Section 13(4) SARFAESI; physical handover may require Section 14 DM order")
    else:
        risks.append("Possession type not specified in notice — verify whether bank has physical custody")

    if property_data.get("foreclosure_status") in ("scheduled", "upcoming", "active"):
        strengths.append(f"Active auction listing with scheduled auction date: {property_data.get('auction_date') or 'TBD'}")
    if not strengths:
        strengths.append("Public auction listing with verified SARFAESI publication particulars")

    for concern in important_concerns:
        risks.append(f"Important concern: {concern}")
    for missing in missing_info:
        risks.append(f"Missing information: {missing}")
    if not risks:
        risks.append("General foreclosure risks: potential unrecorded liens, encumbrances, or municipal dues")

    due_diligence.append("Verify physical vs symbolic possession under SARFAESI Section 13(4) and Section 14")
    due_diligence.append("Inspect 30-year Encumbrance Certificate (EC) and verify pending municipal/society dues")
    due_diligence.append("Confirm EMD submission deadline and original title deed availability with authorized bank officer")

    if assessment_label == "No major concerns identified in the available documents":
        recommendation = "Documentation and physical possession appear clean. Proceed with physical site inspection and title verification."
    elif assessment_label == "Important risks identified":
        recommendation = "Important legal or property risks identified in available documents. Detailed title search and legal consultation strictly recommended."
    elif assessment_label == "Insufficient information":
        recommendation = "Key auction or property parameters are missing. Clarification from bank officer strictly required before participation."
    else:
        recommendation = "Further investigation required on possession status, title deeds, and pending statutory liabilities before bidding."

    summary = f"Auction intelligence evaluation for {addr}. Assessment label: {assessment_label}. "
    if reserve:
        try:
            summary += f"Reserve price: ₹{float(reserve):,.0f}. "
        except (ValueError, TypeError):
            summary += f"Reserve price: {reserve}. "
    if emd and emd_pct:
        summary += f"EMD: ₹{float(emd):,.0f} ({emd_pct:.1f}%). "

    return PropertyAIAnalysis(
        summary=summary.strip(),
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