import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, userEvent, waitFor } from "@/test";
import { server, mockDocument } from "@/test";
import { http, HttpResponse } from "msw";
import { DocumentsPage } from "../Documents";
import { useDocumentsStore } from "@/stores";

const API_BASE = "/api/v1";

describe("DocumentsPage", () => {
  beforeEach(() => {
    // Reset documents store before each test
    useDocumentsStore.setState({
      documents: [],
      isLoading: false,
      error: null,
    });
  });

  describe("rendering", () => {
    it("should render page title", async () => {
      render(<DocumentsPage />);

      expect(screen.getByText("Documents")).toBeInTheDocument();
    });

    it("should render upload area", async () => {
      render(<DocumentsPage />);

      expect(
        screen.getByText(/drag and drop files here/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/select files/i)).toBeInTheDocument();
    });

    it("should show supported file types", async () => {
      render(<DocumentsPage />);

      expect(
        screen.getByText(/supports pdf, docx, txt, md/i)
      ).toBeInTheDocument();
    });
  });

  describe("loading state", () => {
    it("should show loading spinner while fetching documents", async () => {
      // Override handler to delay response
      server.use(
        http.get(`${API_BASE}/documents`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json({
            documents: [],
            total: 0,
          });
        })
      );

      render(<DocumentsPage />);

      // Initially shows loading state - the spinner has animate-spin class
      expect(document.querySelector(".animate-spin")).toBeInTheDocument();

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.getByText(/no documents yet/i)).toBeInTheDocument();
      });
    });
  });

  describe("empty state", () => {
    it("should show empty state message when no documents", async () => {
      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents: [],
            total: 0,
          });
        })
      );

      render(<DocumentsPage />);

      await waitFor(() => {
        expect(
          screen.getByText(/no documents yet\. upload some to get started\./i)
        ).toBeInTheDocument();
      });
    });
  });

  describe("document list", () => {
    it("should render document list when documents exist", async () => {
      const documents = [
        mockDocument({ id: "1", filename: "report.pdf", file_size: 1024000 }),
        mockDocument({ id: "2", filename: "notes.txt", file_size: 2048 }),
      ];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText("report.pdf")).toBeInTheDocument();
        expect(screen.getByText("notes.txt")).toBeInTheDocument();
      });
    });

    it("should display document size formatted correctly", async () => {
      const documents = [
        mockDocument({ id: "1", filename: "large.pdf", file_size: 1048576 }), // 1 MB
        mockDocument({ id: "2", filename: "small.txt", file_size: 512 }), // 512 Bytes
      ];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText("1 MB")).toBeInTheDocument();
        expect(screen.getByText("512 Bytes")).toBeInTheDocument();
      });
    });

    it("should display document status with correct icon", async () => {
      const documents = [
        mockDocument({ id: "1", filename: "ready.pdf", status: "ready" }),
        mockDocument({
          id: "2",
          filename: "processing.pdf",
          status: "processing",
        }),
        mockDocument({ id: "3", filename: "pending.pdf", status: "pending" }),
        mockDocument({ id: "4", filename: "failed.pdf", status: "failed" }),
      ];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText("Ready")).toBeInTheDocument();
        expect(screen.getByText("Processing")).toBeInTheDocument();
        expect(screen.getByText("Pending")).toBeInTheDocument();
        expect(screen.getByText("Failed")).toBeInTheDocument();
      });
    });

    it("should display page count when available", async () => {
      const documents = [
        mockDocument({ id: "1", filename: "multi.pdf", page_count: 25 }),
        mockDocument({ id: "2", filename: "unknown.pdf", page_count: null }),
      ];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText("25")).toBeInTheDocument();
        expect(screen.getByText("-")).toBeInTheDocument();
      });
    });

    it("should show error message for failed documents", async () => {
      const documents = [
        mockDocument({
          id: "1",
          filename: "corrupted.pdf",
          status: "failed",
          error_message: "File is corrupted",
        }),
      ];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText("File is corrupted")).toBeInTheDocument();
      });
    });
  });

  describe("upload interaction", () => {
    it("should have file input for upload", async () => {
      render(<DocumentsPage />);

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toBeInTheDocument();
      expect(fileInput).toHaveAttribute("accept", ".pdf,.docx,.txt,.md");
      expect(fileInput).toHaveAttribute("multiple");
    });

    it("should call upload when file is selected", async () => {
      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({ documents: [], total: 0 });
        }),
        http.post(`${API_BASE}/documents/upload`, () => {
          return HttpResponse.json(
            { document_id: "new-doc", status: "pending" },
            { status: 201 }
          );
        })
      );

      const user = userEvent.setup();
      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no documents yet/i)).toBeInTheDocument();
      });

      const fileInput = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;
      const file = new File(["test content"], "test.pdf", {
        type: "application/pdf",
      });

      await user.upload(fileInput, file);

      // Document should be added to the store
      await waitFor(() => {
        const state = useDocumentsStore.getState();
        expect(state.documents.length).toBeGreaterThan(0);
      });
    });

    it("should show uploading state", async () => {
      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({ documents: [], total: 0 });
        }),
        http.post(`${API_BASE}/documents/upload`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(
            { document_id: "new-doc", status: "pending" },
            { status: 201 }
          );
        })
      );

      const user = userEvent.setup();
      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no documents yet/i)).toBeInTheDocument();
      });

      const fileInput = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;
      const file = new File(["test"], "test.pdf", { type: "application/pdf" });

      user.upload(fileInput, file);

      await waitFor(() => {
        expect(screen.getByText("Uploading...")).toBeInTheDocument();
      });
    });

    it("should handle upload errors", async () => {
      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({ documents: [], total: 0 });
        }),
        http.post(`${API_BASE}/documents/upload`, () => {
          return new HttpResponse(
            JSON.stringify({ detail: "File too large" }),
            { status: 413 }
          );
        })
      );

      const user = userEvent.setup();
      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no documents yet/i)).toBeInTheDocument();
      });

      const fileInput = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;
      const file = new File(["x".repeat(100)], "big.pdf", {
        type: "application/pdf",
      });

      await user.upload(fileInput, file);

      // Error should be displayed
      await waitFor(() => {
        const errorDiv = document.querySelector(".text-error");
        expect(errorDiv).toBeInTheDocument();
      });
    });
  });

  describe("delete interaction", () => {
    it("should have delete button for each document", async () => {
      const documents = [
        mockDocument({ id: "1", filename: "doc1.pdf" }),
        mockDocument({ id: "2", filename: "doc2.pdf" }),
      ];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      render(<DocumentsPage />);

      await waitFor(() => {
        const deleteButtons = screen.getAllByTitle("Delete document");
        expect(deleteButtons).toHaveLength(2);
      });
    });

    it("should show confirmation dialog before delete", async () => {
      const documents = [mockDocument({ id: "1", filename: "doc.pdf" })];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      // Mock window.confirm
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

      const user = userEvent.setup();
      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText("doc.pdf")).toBeInTheDocument();
      });

      const deleteButton = screen.getByTitle("Delete document");
      await user.click(deleteButton);

      expect(confirmSpy).toHaveBeenCalledWith(
        "Are you sure you want to delete this document?"
      );

      confirmSpy.mockRestore();
    });

    it("should delete document when confirmed", async () => {
      const documents = [mockDocument({ id: "doc-1", filename: "delete-me.pdf" })];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        }),
        http.delete(`${API_BASE}/documents/:id`, () => {
          return new HttpResponse(null, { status: 204 });
        })
      );

      // Pre-populate the store
      useDocumentsStore.setState({ documents });

      // Mock window.confirm to return true
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

      const user = userEvent.setup();
      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText("delete-me.pdf")).toBeInTheDocument();
      });

      const deleteButton = screen.getByTitle("Delete document");
      await user.click(deleteButton);

      // Document should be removed
      await waitFor(() => {
        expect(screen.queryByText("delete-me.pdf")).not.toBeInTheDocument();
      });

      confirmSpy.mockRestore();
    });

    it("should not delete document when cancelled", async () => {
      const documents = [mockDocument({ id: "1", filename: "keep-me.pdf" })];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      // Pre-populate the store
      useDocumentsStore.setState({ documents });

      // Mock window.confirm to return false
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

      const user = userEvent.setup();
      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText("keep-me.pdf")).toBeInTheDocument();
      });

      const deleteButton = screen.getByTitle("Delete document");
      await user.click(deleteButton);

      // Document should still be there
      expect(screen.getByText("keep-me.pdf")).toBeInTheDocument();

      confirmSpy.mockRestore();
    });
  });

  describe("error state", () => {
    it("should display fetch error message", async () => {
      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return new HttpResponse(null, { status: 500 });
        })
      );

      render(<DocumentsPage />);

      await waitFor(() => {
        const state = useDocumentsStore.getState();
        expect(state.error).not.toBeNull();
      });
    });
  });

  describe("drag and drop", () => {
    it("should have proper drop zone setup", async () => {
      render(<DocumentsPage />);

      // Verify the drop zone exists and has proper initial classes
      // The drop zone is the parent of the flex container that holds the text
      const dropZoneText = screen.getByText(/drag and drop files here/i);
      const flexContainer = dropZoneText.closest(".flex");
      const dropZone = flexContainer?.parentElement;

      // Initially should have the border-dashed class
      expect(dropZone).toHaveClass("border-dashed");
      expect(dropZone).toHaveClass("border-2");
    });
  });

  describe("polling for status updates", () => {
    it("should poll when documents are processing", async () => {
      let fetchCount = 0;
      const documents = [
        mockDocument({ id: "1", filename: "processing.pdf", status: "processing" }),
      ];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          fetchCount++;
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      render(<DocumentsPage />);

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBeGreaterThanOrEqual(1);
      });

      // The component should start polling when there are processing documents
      // Wait a bit and check if additional fetches occur
      await waitFor(
        () => {
          expect(fetchCount).toBeGreaterThanOrEqual(2);
        },
        { timeout: 5000 }
      );
    });
  });

  describe("table headers", () => {
    it("should render all table column headers", async () => {
      const documents = [mockDocument({ id: "1" })];

      server.use(
        http.get(`${API_BASE}/documents`, () => {
          return HttpResponse.json({
            documents,
            total: documents.length,
          });
        })
      );

      render(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByText("Document")).toBeInTheDocument();
        expect(screen.getByText("Size")).toBeInTheDocument();
        expect(screen.getByText("Status")).toBeInTheDocument();
        expect(screen.getByText("Pages")).toBeInTheDocument();
        expect(screen.getByText("Actions")).toBeInTheDocument();
      });
    });
  });
});
