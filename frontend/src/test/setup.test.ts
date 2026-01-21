import { describe, it, expect } from "vitest";
import { server } from "./setup";
import {
  mockDocument,
  mockThread,
  mockUser,
  mockSearchResult,
  mockHealthStatus,
  mockAdminStats,
} from "./mocks/handlers";

describe("Test Setup", () => {
  it("should have MSW server running", () => {
    expect(server).toBeDefined();
    expect(server.listHandlers().length).toBeGreaterThan(0);
  });

  it("should have vitest globals available", () => {
    expect(describe).toBeDefined();
    expect(it).toBeDefined();
    expect(expect).toBeDefined();
  });
});

describe("Mock Data Factories", () => {
  it("should create mock document with defaults", () => {
    const doc = mockDocument();
    expect(doc.id).toBe("doc-1");
    expect(doc.filename).toBe("test-document.pdf");
    expect(doc.status).toBe("ready");
  });

  it("should create mock document with overrides", () => {
    const doc = mockDocument({ id: "custom-id", status: "processing" });
    expect(doc.id).toBe("custom-id");
    expect(doc.status).toBe("processing");
    expect(doc.filename).toBe("test-document.pdf"); // Default preserved
  });

  it("should create mock thread with defaults", () => {
    const thread = mockThread();
    expect(thread.id).toBe("thread-1");
    expect(thread.name).toBe("Test Thread");
  });

  it("should create mock thread with overrides", () => {
    const thread = mockThread({ name: "Custom Thread" });
    expect(thread.name).toBe("Custom Thread");
  });

  it("should create mock user with defaults", () => {
    const user = mockUser();
    expect(user.id).toBe("user-1");
    expect(user.email).toBe("test@example.com");
    expect(user.role).toBe("user");
    expect(user.is_active).toBe(true);
  });

  it("should create mock user with overrides", () => {
    const user = mockUser({ role: "admin", is_active: false });
    expect(user.role).toBe("admin");
    expect(user.is_active).toBe(false);
  });

  it("should create mock search result with defaults", () => {
    const result = mockSearchResult();
    expect(result.chunk_id).toBe("chunk-1");
    expect(result.document_id).toBe("doc-1");
    expect(result.score).toBe(0.95);
  });

  it("should have valid health status mock", () => {
    expect(mockHealthStatus.api).toBe("ok");
    expect(mockHealthStatus.database).toBe("ok");
    expect(mockHealthStatus.qdrant).toBe("ok");
  });

  it("should have valid admin stats mock", () => {
    expect(mockAdminStats.total_users).toBe(100);
    expect(mockAdminStats.total_documents).toBe(500);
    expect(mockAdminStats.documents_by_status.ready).toBe(480);
  });
});

describe("MSW API Mocking", () => {
  it("should mock health endpoint", async () => {
    const response = await fetch("/api/v1/health");
    const data = await response.json();
    expect(data.api).toBe("ok");
    expect(data.database).toBe("ok");
  });

  it("should mock documents list endpoint", async () => {
    const response = await fetch("/api/v1/documents");
    const data = await response.json();
    expect(data.documents).toBeDefined();
    expect(Array.isArray(data.documents)).toBe(true);
    expect(data.total).toBeDefined();
  });

  it("should mock threads list endpoint", async () => {
    const response = await fetch("/api/v1/chat/threads");
    const data = await response.json();
    expect(data.threads).toBeDefined();
    expect(Array.isArray(data.threads)).toBe(true);
  });

  it("should mock search endpoint", async () => {
    const response = await fetch("/api/v1/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "test query" }),
    });
    const data = await response.json();
    expect(data.results).toBeDefined();
    expect(Array.isArray(data.results)).toBe(true);
  });

  it("should mock admin stats endpoint", async () => {
    const response = await fetch("/api/v1/admin/stats");
    const data = await response.json();
    expect(data.total_users).toBe(100);
  });

  it("should return 404 for non-existent document", async () => {
    const response = await fetch("/api/v1/documents/non-existent-id");
    expect(response.status).toBe(404);
  });

  it("should create new thread via POST", async () => {
    const response = await fetch("/api/v1/chat/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "New Test Thread" }),
    });
    expect(response.status).toBe(201);
    const data = await response.json();
    expect(data.name).toBe("New Test Thread");
  });
});
