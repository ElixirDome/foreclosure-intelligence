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
  estimated_value: number | null;
  property_type: string | null;
  survey_number: string | null;
  discount_percentage: number | null;
  deal_score: number | null;
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
  deal_score: number | null;
  deal_rating: string | null;
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

export interface DealIntelligence {
  property_id: number;
  deal_score: number | null;
  deal_rating: string | null;
  discount_amount: number | null;
  discount_percentage: number | null;
  price_per_sqft: number | null;
  risk_level: number;
  estimated_value: number | null;
  opening_bid: number | null;
  comparable_count: number;
  factors: { direction: string; label: string; detail?: string | null }[];
  explanation: string;
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
