// User types
export interface User {
  id: string;
  email: string;
  role: "user" | "admin" | "superuser";
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Document types
export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface Document {
  id: string;
  filename: string;
  normalized_filename: string;
  file_type: string;
  file_size: number;
  page_count: number | null;
  status: DocumentStatus;
  chunking_strategy: string;
  ocr_enabled: boolean;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  status: DocumentStatus;
}

// Thread and Message types
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  model_used: string | null;
  is_from_documents: boolean;
  created_at: string;
}

export interface Thread {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
}

export interface Citation {
  index: number;
  chunk_id: string;
  document_id: string;
  document_name: string;
  pages: number[];
  excerpt: string;
}

// Search types
export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_name: string;
  content: string;
  page_numbers: number[];
  score: number;
}

// SSE Event types for chat streaming
export type SSEStatus = "searching" | "thinking" | "generating";

export interface SSEStatusEvent {
  event: "status";
  data: { stage: SSEStatus };
}

export interface SSETokenEvent {
  event: "token";
  data: { content: string };
}

export interface SSECitationEvent {
  event: "citation";
  data: Citation;
}

export interface SSEDoneEvent {
  event: "done";
  data: {
    message_id: string;
    is_from_documents: boolean;
    content: string;
  };
}

export interface SSEErrorEvent {
  event: "error";
  data: { code: string; message: string };
}

export type SSEEvent =
  | SSEStatusEvent
  | SSETokenEvent
  | SSECitationEvent
  | SSEDoneEvent
  | SSEErrorEvent;

// Admin types
export interface AdminStats {
  total_users: number;
  active_users_today: number;
  total_documents: number;
  total_queries_today: number;
  documents_by_status: {
    pending: number;
    processing: number;
    ready: number;
    failed: number;
  };
}

export interface HealthStatus {
  api: "ok" | "degraded";
  database: "ok" | "error";
  qdrant: "ok" | "error";
}

// API response wrappers
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface ThreadsResponse {
  threads: Thread[];
  total: number;
}

export interface SearchResponse {
  results: SearchResult[];
}
