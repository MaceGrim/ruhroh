import axios, { type AxiosInstance, type AxiosError } from "axios";
import type {
  Document,
  DocumentUploadResponse,
  Thread,
  ThreadsResponse,
  SearchResult,
  HealthStatus,
  AdminStats,
  User,
} from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        "Content-Type": "application/json",
      },
    });

    // Add auth token to requests
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem("auth_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Handle auth errors
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          localStorage.removeItem("auth_token");
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }
    );
  }

  // Health
  async getHealth(): Promise<HealthStatus> {
    const { data } = await this.client.get<HealthStatus>("/health");
    return data;
  }

  // Auth
  setAuthToken(token: string): void {
    localStorage.setItem("auth_token", token);
  }

  clearAuthToken(): void {
    localStorage.removeItem("auth_token");
  }

  // Documents
  async getDocuments(): Promise<Document[]> {
    const { data } = await this.client.get<Document[]>("/documents");
    return data;
  }

  async getDocument(id: string): Promise<Document> {
    const { data } = await this.client.get<Document>(`/documents/${id}`);
    return data;
  }

  async uploadDocument(file: File): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const { data } = await this.client.post<DocumentUploadResponse>(
      "/documents",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return data;
  }

  async deleteDocument(id: string): Promise<void> {
    await this.client.delete(`/documents/${id}`);
  }

  // Threads
  async getThreads(limit = 20, offset = 0): Promise<ThreadsResponse> {
    const { data } = await this.client.get<ThreadsResponse>("/chat/threads", {
      params: { limit, offset },
    });
    return data;
  }

  async getThread(id: string): Promise<Thread> {
    const { data } = await this.client.get<Thread>(`/chat/threads/${id}`);
    return data;
  }

  async createThread(name?: string): Promise<Thread> {
    const { data } = await this.client.post<Thread>("/chat/threads", { name });
    return data;
  }

  async deleteThread(id: string): Promise<void> {
    await this.client.delete(`/chat/threads/${id}`);
  }

  // Chat streaming - returns EventSource URL
  getChatStreamUrl(threadId: string): string {
    return `${API_BASE_URL}/chat/threads/${threadId}/messages`;
  }

  async sendMessage(
    threadId: string,
    content: string,
    model?: string
  ): Promise<Response> {
    const token = localStorage.getItem("auth_token");
    return fetch(`${API_BASE_URL}/chat/threads/${threadId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content, model }),
    });
  }

  // Search
  async search(
    query: string,
    options?: {
      top_k?: number;
      document_ids?: string[];
      use_keyword?: boolean;
      use_vector?: boolean;
    }
  ): Promise<SearchResult[]> {
    const { data } = await this.client.post<{ results: SearchResult[] }>(
      "/search",
      {
        query,
        ...options,
      }
    );
    return data.results;
  }

  // Admin
  async getAdminStats(): Promise<AdminStats> {
    const { data } = await this.client.get<AdminStats>("/admin/stats");
    return data;
  }

  async getUsers(): Promise<User[]> {
    const { data } = await this.client.get<User[]>("/admin/users");
    return data;
  }

  async updateUser(
    id: string,
    updates: { role?: string; is_active?: boolean }
  ): Promise<User> {
    const { data } = await this.client.patch<User>(
      `/admin/users/${id}`,
      updates
    );
    return data;
  }
}

export const api = new ApiClient();
