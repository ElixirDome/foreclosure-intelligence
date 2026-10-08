import api from "./client";
import type {
  DealIntelligence,
  DocumentItem,
  EvidenceItem,
  RAGResponse,
  RetrievedChunk,
} from "./types";

export async function askRag(params: {
  question: string;
  property_id?: number | null;
  document_id?: number | null;
  mode?: "keyword" | "vector" | "hybrid";
  multi_source?: boolean | null;
  limit?: number;
}): Promise<RAGResponse> {
  const { data } = await api.post<RAGResponse>("/documents/rag", {
    question: params.question,
    property_id: params.property_id ?? null,
    document_id: params.document_id ?? null,
    mode: params.mode ?? "hybrid",
    multi_source: params.multi_source ?? null,
    limit: params.limit ?? 6,
  });
  return data;
}

export async function analyzeInvestment(params: {
  property_id: number;
  question?: string;
  mode?: "keyword" | "vector" | "hybrid";
}): Promise<RAGResponse> {
  const { data } = await api.post<RAGResponse>("/documents/rag/investment", {
    property_id: params.property_id,
    question: params.question ?? null,
    mode: params.mode ?? "hybrid",
  });
  return data;
}

export async function retrieveChunks(params: {
  query: string;
  document_id?: number | null;
  mode?: "keyword" | "vector" | "hybrid";
  limit?: number;
}): Promise<RetrievedChunk[]> {
  const { data } = await api.post<RetrievedChunk[]>("/documents/retrieve", {
    query: params.query,
    document_id: params.document_id ?? null,
    mode: params.mode ?? "hybrid",
    limit: params.limit ?? 8,
  });
  return data;
}

export async function listDocuments(limit = 50): Promise<DocumentItem[]> {
  const { data } = await api.get<DocumentItem[]>("/documents/", {
    params: { limit },
  });
  return data;
}

export async function getPropertyEvidence(
  propertyId: number,
): Promise<EvidenceItem[]> {
  const { data } = await api.get<EvidenceItem[]>(
    `/properties/${propertyId}/evidence`,
  );
  return data;
}

export async function getPropertyDeal(
  propertyId: number,
): Promise<DealIntelligence> {
  const { data } = await api.get<DealIntelligence>(
    `/properties/${propertyId}/deal`,
  );
  return data;
}
