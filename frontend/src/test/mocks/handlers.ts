import { http, HttpResponse } from "msw";
import type {
  Document,
  Thread,
  HealthStatus,
  AdminStats,
  User,
  SearchResult,
  ThreadsResponse,
  DocumentUploadResponse,
} from "@/types";

const API_BASE = "/api/v1";

// Mock data factories
export const mockDocument = (overrides?: Partial<Document>): Document => ({
  id: "doc-1",
  filename: "test-document.pdf",
  normalized_filename: "test_document.pdf",
  file_type: "application/pdf",
  file_size: 1024000,
  page_count: 10,
  status: "ready",
  chunking_strategy: "semantic",
  ocr_enabled: false,
  error_message: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  ...overrides,
});

export const mockThread = (overrides?: Partial<Thread>): Thread => ({
  id: "thread-1",
  name: "Test Thread",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  messages: [],
  ...overrides,
});

export const mockUser = (overrides?: Partial<User>): User => ({
  id: "user-1",
  email: "test@example.com",
  role: "user",
  is_active: true,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  ...overrides,
});

export const mockSearchResult = (
  overrides?: Partial<SearchResult>
): SearchResult => ({
  chunk_id: "chunk-1",
  document_id: "doc-1",
  document_name: "test-document.pdf",
  content: "This is a test content snippet from the document.",
  page_numbers: [1, 2],
  score: 0.95,
  ...overrides,
});

export const mockHealthStatus: HealthStatus = {
  api: "ok",
  database: "ok",
  qdrant: "ok",
};

export const mockAdminStats: AdminStats = {
  total_users: 100,
  active_users_today: 25,
  total_documents: 500,
  total_queries_today: 150,
  documents_by_status: {
    pending: 5,
    processing: 10,
    ready: 480,
    failed: 5,
  },
};

// Default mock documents and threads for list endpoints
const mockDocuments: Document[] = [
  mockDocument({ id: "doc-1", filename: "document-1.pdf" }),
  mockDocument({ id: "doc-2", filename: "document-2.pdf" }),
  mockDocument({
    id: "doc-3",
    filename: "document-3.pdf",
    status: "processing",
  }),
];

const mockThreads: Thread[] = [
  mockThread({ id: "thread-1", name: "First Thread" }),
  mockThread({ id: "thread-2", name: "Second Thread" }),
];

const mockUsers: User[] = [
  mockUser({ id: "user-1", email: "user1@example.com", role: "user" }),
  mockUser({ id: "user-2", email: "admin@example.com", role: "admin" }),
];

// MSW Request Handlers
export const handlers = [
  // Health endpoint
  http.get(`${API_BASE}/health`, () => {
    return HttpResponse.json(mockHealthStatus);
  }),

  // Documents endpoints
  http.get(`${API_BASE}/documents`, () => {
    return HttpResponse.json({
      documents: mockDocuments,
      total: mockDocuments.length,
    });
  }),

  http.get(`${API_BASE}/documents/:id`, ({ params }) => {
    const doc = mockDocuments.find((d) => d.id === params.id);
    if (!doc) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(doc);
  }),

  http.post(`${API_BASE}/documents/upload`, () => {
    const response: DocumentUploadResponse = {
      document_id: "new-doc-id",
      status: "pending",
    };
    return HttpResponse.json(response, { status: 201 });
  }),

  http.delete(`${API_BASE}/documents/:id`, ({ params }) => {
    const exists = mockDocuments.some((d) => d.id === params.id);
    if (!exists) {
      return new HttpResponse(null, { status: 404 });
    }
    return new HttpResponse(null, { status: 204 });
  }),

  // Threads endpoints
  http.get(`${API_BASE}/chat/threads`, ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get("limit") || "20", 10);
    const offset = parseInt(url.searchParams.get("offset") || "0", 10);

    const paginatedThreads = mockThreads.slice(offset, offset + limit);
    const response: ThreadsResponse = {
      threads: paginatedThreads,
      total: mockThreads.length,
    };
    return HttpResponse.json(response);
  }),

  http.get(`${API_BASE}/chat/threads/:id`, ({ params }) => {
    const thread = mockThreads.find((t) => t.id === params.id);
    if (!thread) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(thread);
  }),

  http.post(`${API_BASE}/chat/threads`, async ({ request }) => {
    const body = (await request.json()) as { name?: string };
    const newThread = mockThread({
      id: `thread-${Date.now()}`,
      name: body.name || "New Thread",
    });
    return HttpResponse.json(newThread, { status: 201 });
  }),

  http.delete(`${API_BASE}/chat/threads/:id`, ({ params }) => {
    const exists = mockThreads.some((t) => t.id === params.id);
    if (!exists) {
      return new HttpResponse(null, { status: 404 });
    }
    return new HttpResponse(null, { status: 204 });
  }),

  // Chat message streaming - returns a simple response for testing
  // Note: Actual SSE streaming would need special handling
  http.post(`${API_BASE}/chat/threads/:id/messages`, async () => {
    // For unit tests, return a simple successful response
    // Integration tests should mock the actual streaming behavior
    return new HttpResponse(
      `data: {"event":"done","data":{"message_id":"msg-1","is_from_documents":true,"content":"Test response"}}\n\n`,
      {
        headers: {
          "Content-Type": "text/event-stream",
        },
      }
    );
  }),

  // Search endpoint
  http.post(`${API_BASE}/search`, async ({ request }) => {
    const body = (await request.json()) as { query: string };
    const results = body.query
      ? [
          mockSearchResult({
            content: `Result for: ${body.query}`,
          }),
        ]
      : [];
    return HttpResponse.json({ results });
  }),

  // Admin endpoints
  http.get(`${API_BASE}/admin/stats`, () => {
    return HttpResponse.json(mockAdminStats);
  }),

  http.get(`${API_BASE}/admin/users`, () => {
    return HttpResponse.json(mockUsers);
  }),

  http.patch(`${API_BASE}/admin/users/:id`, async ({ params, request }) => {
    const user = mockUsers.find((u) => u.id === params.id);
    if (!user) {
      return new HttpResponse(null, { status: 404 });
    }
    const updates = (await request.json()) as {
      role?: string;
      is_active?: boolean;
    };
    return HttpResponse.json({ ...user, ...updates });
  }),
];

// Export for use in tests that need to customize handlers
export { mockDocuments, mockThreads, mockUsers };
