/** Shared API types aligned with the backend document-centric RAG API. */

export interface Property {
  id: number;
  address: string;
  city?: string | null;
  locality?: string | null;
  price: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  area_sqft: number | null;
  auction_date: string | null;
  foreclosure_status: string | null;
  opening_bid: number | null;
  reserve_price?: number | null;
  emd?: number | null;
  emd_percentage?: number | null;
  reserve_price_per_sqft?: number | null;
  property_type: string | null;
  survey_number: string | null;
  possession_type?: string | null;
  bank_name?: string | null;
  branch_name?: string | null;
  market_valuation_status?: string | null;
  estimated_value?: number | null;
  discount_percentage?: number | null;
  deal_score?: number | null;
}

export interface Citation {
  kind: string;
  source_id?: string | null;
  title?: string | null;
  excerpt: string;
  score: number;
  document_id?: number | null;
  chunk_id?: number | null;
  page_number?: number | null;
  property_id?: number | null;
  filename?: string | null;
  source_name?: string | null;
}

export interface StructuredAnalysis {
  summary: string;
  strengths: string[];
  risks: string[];
  due_diligence: string[];
  recommendation: string;
  assessment_label?: string | null;
  deal_score?: number | null;
  deal_rating?: string | null;
}

export interface RAGResponse {
  question: string;
  answer: string;
  citations: Citation[];
  structured?: StructuredAnalysis | null;
  context_kinds: string[];
  property_ids: number[];
  document_ids: number[];
  chunks_used: number;
  method: string;
  mode: string;
  llm_provider?: string;
}

export interface EvidenceItem {
  id: number;
  property_id: number;
  document_id: number;
  document_chunk_id: number | null;
  field: string;
  value: string;
  page_number: number | null;
  source_text: string | null;
  extraction_method: string | null;
  confidence: number | null;
}

export interface PropertyAnalysis {
  reserve_price: number | null;
  emd: number | null;
  emd_percentage: number | null;
  area_sqft: number | null;
  reserve_price_per_sqft: number | null;
  disclosed_outstanding_dues: string | number | null;
  other_financial_obligations: string[];
  market_valuation_status: string;

  auction_date: string | null;
  auction_start: string | null;
  auction_end: string | null;
  emd_deadline: string | null;
  inspection_start: string | null;
  inspection_end: string | null;
  inspection_window: string | null;
  auction_status: string | null;
  bank_name: string | null;
  branch_name: string | null;
  contact_details: string | null;
  auction_platform: string | null;

  possession_type: string | null;
  disclosed_encumbrances: string[];
  pending_litigation: string[];
  title_concerns: string[];
  property_discrepancies: string[];
  missing_documentation: string[];
  bank_conditions: string[];

  assessment_label: string;
  important_concerns: string[];
  missing_information: string[];
  financial_considerations: string[];
  possession_concerns: string[];
  procedural_considerations: string[];
  summary: string;

  opening_bid?: number | null;
  estimated_value?: number | null;
  discount_amount?: number | null;
  discount_percentage?: number | null;
  price_per_sqft?: number | null;
  potential_upside?: number | null;
  deal_score?: number | null;
  deal_rating?: string | null;
  valuation_confidence?: number | null;
  risk_level?: number | null;
}

export interface DealIntelligence {
  property_id: number;
  assessment_label: string;
  reserve_price: number | null;
  emd: number | null;
  emd_percentage: number | null;
  property_area: number | null;
  reserve_price_per_sqft: number | null;
  disclosed_outstanding_dues: string | number | null;
  possession_type: string;
  auction_status: string | null;
  factors: { direction: string; label: string; detail?: string | null }[];
  explanation: string;
  market_valuation_status: string;
  deal_score?: number | null;
  deal_rating?: string | null;
  discount_amount?: number | null;
  discount_percentage?: number | null;
  price_per_sqft?: number | null;
  risk_level?: number;
  estimated_value?: number | null;
  opening_bid?: number | null;
  comparable_count?: number;
}

export interface DocumentItem {
  id: number;
  source_name: string;
  source_url: string;
  document_type: string;
  title: string | null;
  filename: string | null;
  mime_type: string | null;
  storage_path: string | null;
  content_hash: string | null;
  first_seen_at: string;
  last_seen_at: string;
}

export interface RetrievedChunk {
  chunk_id: number;
  document_id: number;
  chunk_index: number;
  page_number: number | null;
  text: string;
  score: number;
  method: string;
  document_title?: string | null;
  source_name?: string | null;
  filename?: string | null;
}
