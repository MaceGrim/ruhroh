import { describe, it, expect, beforeEach, vi } from "vitest";
import { useDocumentsStore } from "../documents";
import { api } from "@/services/api";
import { mockDocument } from "@/test";

// Mock the api module
vi.mock("@/services/api", () => ({
  api: {
    getDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("useDocumentsStore", () => {
  beforeEach(() => {
    // Reset store state before each test
    useDocumentsStore.setState({
      documents: [],
      isLoading: false,
      error: null,
    });
    vi.clearAllMocks();
  });

  describe("initial state", () => {
    it("should have empty documents array initially", () => {
      const state = useDocumentsStore.getState();
      expect(state.documents).toEqual([]);
    });

    it("should have isLoading false initially", () => {
      const state = useDocumentsStore.getState();
      expect(state.isLoading).toBe(false);
    });

    it("should have error null initially", () => {
      const state = useDocumentsStore.getState();
      expect(state.error).toBeNull();
    });
  });

  describe("fetchDocuments", () => {
    it("should set isLoading to true while fetching", async () => {
      mockedApi.getDocuments.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve([]), 100))
      );

      const fetchPromise = useDocumentsStore.getState().fetchDocuments();

      expect(useDocumentsStore.getState().isLoading).toBe(true);

      await fetchPromise;
    });

    it("should fetch documents and update state", async () => {
      const documents = [
        mockDocument({ id: "1", filename: "doc1.pdf" }),
        mockDocument({ id: "2", filename: "doc2.pdf" }),
      ];
      mockedApi.getDocuments.mockResolvedValue(documents);

      await useDocumentsStore.getState().fetchDocuments();

      const state = useDocumentsStore.getState();
      expect(state.documents).toEqual(documents);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
    });

    it("should clear error on successful fetch", async () => {
      // Set an initial error
      useDocumentsStore.setState({ error: "Previous error" });

      mockedApi.getDocuments.mockResolvedValue([]);

      await useDocumentsStore.getState().fetchDocuments();

      expect(useDocumentsStore.getState().error).toBeNull();
    });

    it("should set error on fetch failure", async () => {
      const errorMessage = "Network error";
      mockedApi.getDocuments.mockRejectedValue(new Error(errorMessage));

      await useDocumentsStore.getState().fetchDocuments();

      const state = useDocumentsStore.getState();
      expect(state.error).toBe(errorMessage);
      expect(state.isLoading).toBe(false);
      expect(state.documents).toEqual([]);
    });

    it("should handle non-Error rejections", async () => {
      mockedApi.getDocuments.mockRejectedValue("Unknown error");

      await useDocumentsStore.getState().fetchDocuments();

      const state = useDocumentsStore.getState();
      expect(state.error).toBe("Failed to fetch documents");
    });

    it("should call api.getDocuments", async () => {
      mockedApi.getDocuments.mockResolvedValue([]);

      await useDocumentsStore.getState().fetchDocuments();

      expect(mockedApi.getDocuments).toHaveBeenCalledTimes(1);
    });
  });

  describe("uploadDocument", () => {
    it("should upload a document and add it to the store", async () => {
      const file = new File(["test content"], "test.pdf", {
        type: "application/pdf",
      });
      mockedApi.uploadDocument.mockResolvedValue({
        document_id: "new-doc-id",
        status: "pending",
      });

      const result = await useDocumentsStore.getState().uploadDocument(file);

      expect(result.id).toBe("new-doc-id");
      expect(result.filename).toBe("test.pdf");
      expect(result.status).toBe("pending");
      expect(useDocumentsStore.getState().documents).toHaveLength(1);
    });

    it("should call api.uploadDocument with the file", async () => {
      const file = new File(["content"], "upload.pdf", {
        type: "application/pdf",
      });
      mockedApi.uploadDocument.mockResolvedValue({
        document_id: "doc-id",
        status: "pending",
      });

      await useDocumentsStore.getState().uploadDocument(file);

      expect(mockedApi.uploadDocument).toHaveBeenCalledWith(file);
      expect(mockedApi.uploadDocument).toHaveBeenCalledTimes(1);
    });

    it("should add document to existing documents", async () => {
      // Pre-populate with existing documents
      const existingDocs = [mockDocument({ id: "existing-1" })];
      useDocumentsStore.setState({ documents: existingDocs });

      const file = new File(["new"], "new.pdf", { type: "application/pdf" });
      mockedApi.uploadDocument.mockResolvedValue({
        document_id: "new-doc",
        status: "pending",
      });

      await useDocumentsStore.getState().uploadDocument(file);

      const docs = useDocumentsStore.getState().documents;
      expect(docs).toHaveLength(2);
      expect(docs[0].id).toBe("existing-1");
      expect(docs[1].id).toBe("new-doc");
    });

    it("should set correct file metadata on uploaded document", async () => {
      const file = new File(["x".repeat(1000)], "large-file.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });
      mockedApi.uploadDocument.mockResolvedValue({
        document_id: "doc-id",
        status: "pending",
      });

      const result = await useDocumentsStore.getState().uploadDocument(file);

      expect(result.filename).toBe("large-file.docx");
      expect(result.file_type).toBe("docx");
      expect(result.file_size).toBe(1000);
    });

    it("should propagate upload errors", async () => {
      const file = new File(["test"], "test.pdf", { type: "application/pdf" });
      mockedApi.uploadDocument.mockRejectedValue(new Error("Upload failed"));

      await expect(
        useDocumentsStore.getState().uploadDocument(file)
      ).rejects.toThrow("Upload failed");
    });
  });

  describe("deleteDocument", () => {
    it("should delete a document from the store", async () => {
      const docs = [
        mockDocument({ id: "doc-1" }),
        mockDocument({ id: "doc-2" }),
      ];
      useDocumentsStore.setState({ documents: docs });
      mockedApi.deleteDocument.mockResolvedValue();

      await useDocumentsStore.getState().deleteDocument("doc-1");

      const remaining = useDocumentsStore.getState().documents;
      expect(remaining).toHaveLength(1);
      expect(remaining[0].id).toBe("doc-2");
    });

    it("should call api.deleteDocument with correct id", async () => {
      useDocumentsStore.setState({
        documents: [mockDocument({ id: "doc-to-delete" })],
      });
      mockedApi.deleteDocument.mockResolvedValue();

      await useDocumentsStore.getState().deleteDocument("doc-to-delete");

      expect(mockedApi.deleteDocument).toHaveBeenCalledWith("doc-to-delete");
      expect(mockedApi.deleteDocument).toHaveBeenCalledTimes(1);
    });

    it("should propagate delete errors", async () => {
      useDocumentsStore.setState({ documents: [mockDocument({ id: "doc-1" })] });
      mockedApi.deleteDocument.mockRejectedValue(new Error("Delete failed"));

      await expect(
        useDocumentsStore.getState().deleteDocument("doc-1")
      ).rejects.toThrow("Delete failed");
    });

    it("should not remove document if delete fails", async () => {
      const docs = [mockDocument({ id: "doc-1" })];
      useDocumentsStore.setState({ documents: docs });
      mockedApi.deleteDocument.mockRejectedValue(new Error("Delete failed"));

      try {
        await useDocumentsStore.getState().deleteDocument("doc-1");
      } catch {
        // Expected to throw
      }

      // Document should still be in store since delete failed before state update
      // Actually, the implementation calls api first then updates state, so if api fails
      // the state is never updated
      expect(useDocumentsStore.getState().documents).toHaveLength(1);
    });
  });

  describe("updateDocument", () => {
    it("should update a document in the store", () => {
      const doc = mockDocument({ id: "doc-1", filename: "original.pdf" });
      useDocumentsStore.setState({ documents: [doc] });

      useDocumentsStore.getState().updateDocument("doc-1", {
        filename: "updated.pdf",
        status: "ready",
      });

      const updated = useDocumentsStore.getState().documents[0];
      expect(updated.filename).toBe("updated.pdf");
      expect(updated.status).toBe("ready");
      expect(updated.id).toBe("doc-1"); // ID unchanged
    });

    it("should not affect other documents when updating", () => {
      const docs = [
        mockDocument({ id: "doc-1", filename: "doc1.pdf" }),
        mockDocument({ id: "doc-2", filename: "doc2.pdf" }),
      ];
      useDocumentsStore.setState({ documents: docs });

      useDocumentsStore.getState().updateDocument("doc-1", {
        filename: "updated.pdf",
      });

      const allDocs = useDocumentsStore.getState().documents;
      expect(allDocs[0].filename).toBe("updated.pdf");
      expect(allDocs[1].filename).toBe("doc2.pdf"); // Unchanged
    });

    it("should handle updating non-existent document gracefully", () => {
      const doc = mockDocument({ id: "doc-1" });
      useDocumentsStore.setState({ documents: [doc] });

      // This shouldn't throw - just doesn't match any document
      useDocumentsStore.getState().updateDocument("non-existent", {
        filename: "new.pdf",
      });

      // Original document unchanged
      expect(useDocumentsStore.getState().documents[0].id).toBe("doc-1");
    });
  });

  describe("state updates", () => {
    it("should maintain document order after operations", async () => {
      const docs = [
        mockDocument({ id: "doc-1", filename: "first.pdf" }),
        mockDocument({ id: "doc-2", filename: "second.pdf" }),
        mockDocument({ id: "doc-3", filename: "third.pdf" }),
      ];
      useDocumentsStore.setState({ documents: docs });

      // Update middle document
      useDocumentsStore.getState().updateDocument("doc-2", {
        status: "processing",
      });

      const result = useDocumentsStore.getState().documents;
      expect(result[0].id).toBe("doc-1");
      expect(result[1].id).toBe("doc-2");
      expect(result[2].id).toBe("doc-3");
    });

    it("should handle multiple rapid operations", async () => {
      mockedApi.uploadDocument.mockImplementation(async () => ({
        document_id: `doc-${Date.now()}`,
        status: "pending" as const,
      }));

      const file1 = new File(["1"], "file1.pdf", { type: "application/pdf" });
      const file2 = new File(["2"], "file2.pdf", { type: "application/pdf" });
      const file3 = new File(["3"], "file3.pdf", { type: "application/pdf" });

      await Promise.all([
        useDocumentsStore.getState().uploadDocument(file1),
        useDocumentsStore.getState().uploadDocument(file2),
        useDocumentsStore.getState().uploadDocument(file3),
      ]);

      expect(useDocumentsStore.getState().documents).toHaveLength(3);
    });
  });
});
