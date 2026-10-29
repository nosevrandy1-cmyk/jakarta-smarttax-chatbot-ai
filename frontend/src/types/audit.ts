export type TaxDomainCode = "PBB-P2" | "JPB" | "PBJT" | "BPHTB" | "REKLAME" | "PAT";

export type RagSourceType = "pdf_regulasi" | "excel_data" | "user_reasoning";

export type BenchmarkStatus = "PASS" | "PARTIAL" | "FAIL";

export interface HardwareTelemetry {
  system: string | null;
  gpu: string | null;
  vram_gb: number | null;
  primary_llm: string;
  embedding_model: string;
  flash_attention: boolean;
  kv_cache_type: string;
  num_ctx: number;
  temperature: number;
  top_p: number;
  top_k: number;
  ollama_online: boolean;
  installed_models: string[];
}

export interface RecentSourceEntry {
  source_type: RagSourceType;
  doc_name: string;
  domain: string;
  contributor: string;
  ingested_at: string;
}

export interface VectorStoreTelemetry {
  collection: string;
  persist_dir: string;
  distance_metric: string;
  total_chunks: number;
  total_documents: number;
  by_source_type: Record<RagSourceType, number>;
  domain_matrix: Record<TaxDomainCode, Record<RagSourceType, number>>;
  covered_slots: number;
  total_slots: number;
  full_domains_count: number;
  domain_coverage_percentage: number;
  recent_sources: RecentSourceEntry[];
  last_ingested_source: RecentSourceEntry | null;
}

export interface RetrievedSourceCitation {
  chunk_id: string;
  source_type: RagSourceType;
  doc_name: string;
  domain: string;
  contributor: string;
  similarity: number;
  cosine_distance: number;
  excerpt: string;
}

export interface IngestedSourceMeta {
  doc_name: string;
  source_type: RagSourceType;
  contributor: string;
  domain: string;
}

export interface GoldenAuditItem {
  id: string;
  domain: TaxDomainCode;
  tema_pajak: string;
  kategori: string;
  pertanyaan: string;
  kunci_jawaban: string;
  referensi_regulasi: string;
  previous_answer: string;
  previous_score: number;
  current_answer: string;
  current_score: number;
  score_delta: number;
  cosine_similarity_pct: number;
  keyword_hit_ratio_pct: number;
  faithfulness_pct: number;
  retrieval_precision_pct: number;
  matched_keywords: string[];
  missing_keywords: string[];
  status: BenchmarkStatus;
  retrieved_sources: RetrievedSourceCitation[];
  ingested_source_meta: IngestedSourceMeta;
}

export interface EvaluationSnapshot {
  snapshot_id: string;
  timestamp: string;
  trigger_event: string;
  smarttax_iq_percentage: number;
  delta_change: number;
  golden_eval_accuracy: number;
  faithfulness_score: number;
  retrieval_precision: number;
  domain_coverage: number;
  total_chunks_indexed: number;
  ingested_source_meta: IngestedSourceMeta;
  items: GoldenAuditItem[];
}

export interface HistoryTimelinePoint {
  snapshot_id: string;
  timestamp: string;
  trigger_event: string;
  smarttax_iq_percentage: number;
  delta_change: number;
  golden_eval_accuracy: number;
  faithfulness_score: number;
  retrieval_precision: number;
  domain_coverage: number;
  total_chunks_indexed: number;
}

export interface DashboardTelemetryState {
  hardware: HardwareTelemetry;
  vector_store: VectorStoreTelemetry;
  latest_snapshot: EvaluationSnapshot | null;
  evaluation_readiness: { ready: boolean; source_chunks: number; golden_items: number; reason: string };
  history_timeline: HistoryTimelinePoint[];
}

export interface LearnReasoningInput {
  pertanyaan_kasus: string;
  alur_penalaran: string;
  jawaban_final: string;
  topik_pajak: TaxDomainCode;
  kontributor: string;
}
