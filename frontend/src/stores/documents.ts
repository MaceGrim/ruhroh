import { create } from "zustand";
import type { Document } from "@/types";
import { api } from "@/services/api";

interface DocumentsState {
  documents: Document[];
  isLoading: boolean;
  error: string | null;
  fetchDocuments: () => Promise<void>;
  uploadDocument: (file: File) => Promise<Document>;
  deleteDocument: (id: string) => Promise<void>;
  updateDocument: (id: string, updates: Partial<Document>) => void;
}

export const useDocumentsStore = create<DocumentsState>((set, get) => ({
  documents: [],
  isLoading: false,
  error: null,

  fetchDocuments: async () => {
    set({ isLoading: true, error: null });
    try {
      const documents = await api.getDocuments();
      set({ documents, isLoading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to fetch documents",
        isLoading: false,
      });
    }
  },

  uploadDocument: async (file: File) => {
    const response = await api.uploadDocument(file);
    const newDoc: Document = {
      id: response.id,
      filename: response.filename,
      content_type: file.type,
      size_bytes: file.size,
      status: response.status,
      error_message: null,
      chunk_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    set({ documents: [...get().documents, newDoc] });
    return newDoc;
  },

  deleteDocument: async (id: string) => {
    await api.deleteDocument(id);
    set({ documents: get().documents.filter((d) => d.id !== id) });
  },

  updateDocument: (id: string, updates: Partial<Document>) => {
    set({
      documents: get().documents.map((d) =>
        d.id === id ? { ...d, ...updates } : d
      ),
    });
  },
}));
