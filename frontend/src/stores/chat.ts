import { create } from "zustand";
import type { Thread, Message, Citation, SSEStatus } from "@/types";
import { api } from "@/services/api";

interface ChatState {
  threads: Thread[];
  currentThread: Thread | null;
  isLoadingThreads: boolean;
  isSending: boolean;
  streamStatus: SSEStatus | null;
  streamingContent: string;
  streamingCitations: Citation[];
  error: string | null;

  fetchThreads: () => Promise<void>;
  selectThread: (threadId: string) => Promise<void>;
  createThread: (name?: string) => Promise<Thread>;
  deleteThread: (id: string) => Promise<void>;
  sendMessage: (content: string, model?: string) => Promise<void>;
  clearStreamingState: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  threads: [],
  currentThread: null,
  isLoadingThreads: false,
  isSending: false,
  streamStatus: null,
  streamingContent: "",
  streamingCitations: [],
  error: null,

  fetchThreads: async () => {
    set({ isLoadingThreads: true, error: null });
    try {
      const { threads } = await api.getThreads();
      set({ threads, isLoadingThreads: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to fetch threads",
        isLoadingThreads: false,
      });
    }
  },

  selectThread: async (threadId: string) => {
    // Clear streaming state when switching threads
    set({
      streamStatus: null,
      streamingContent: "",
      streamingCitations: [],
      isSending: false,
    });

    try {
      const thread = await api.getThread(threadId);
      set({ currentThread: thread });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load thread",
      });
    }
  },

  createThread: async (name?: string) => {
    const thread = await api.createThread(name);
    set({ threads: [thread, ...get().threads], currentThread: thread });
    return thread;
  },

  deleteThread: async (id: string) => {
    await api.deleteThread(id);
    const { threads, currentThread } = get();
    set({
      threads: threads.filter((t) => t.id !== id),
      currentThread: currentThread?.id === id ? null : currentThread,
    });
  },

  sendMessage: async (content: string, model?: string) => {
    const { currentThread } = get();
    if (!currentThread) return;

    // Add user message to current thread
    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: "user",
      content,
      citations: null,
      model_used: null,
      is_from_documents: false,
      created_at: new Date().toISOString(),
    };

    set({
      currentThread: {
        ...currentThread,
        messages: [...(currentThread.messages || []), userMessage],
      },
      isSending: true,
      streamingContent: "",
      streamingCitations: [],
      error: null,
    });

    try {
      const response = await api.sendMessage(currentThread.id, content, model);

      if (!response.ok || !response.body) {
        throw new Error("Failed to send message");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        // Process any data we received (even on final chunk)
        if (value) {
          buffer += decoder.decode(value, { stream: !done });
        }

        // If stream is done, flush any remaining buffer content
        if (done) {
          buffer += decoder.decode(); // Flush decoder
        }

        const lines = buffer.split("\n");
        buffer = done ? "" : lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            // Event type parsed but not used - data parsing handles event types
            continue;
          }
          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              if (data.message_id) {
                // Done event - finalize the message (check first since done has content too)
                const assistantMessage: Message = {
                  id: data.message_id,
                  role: "assistant",
                  content: data.content || get().streamingContent,
                  citations:
                    get().streamingCitations.length > 0
                      ? get().streamingCitations
                      : null,
                  model_used: model || null,
                  is_from_documents: data.is_from_documents,
                  created_at: new Date().toISOString(),
                };

                const thread = get().currentThread;
                if (thread) {
                  set({
                    currentThread: {
                      ...thread,
                      messages: [...(thread.messages || []), assistantMessage],
                    },
                    isSending: false,
                    streamStatus: null,
                    streamingContent: "",
                    streamingCitations: [],
                  });
                }
              } else if (data.stage) {
                set({ streamStatus: data.stage });
              } else if (data.content !== undefined) {
                set({
                  streamingContent: get().streamingContent + data.content,
                });
              } else if (data.index !== undefined && data.chunk_id) {
                // Citation
                set({
                  streamingCitations: [...get().streamingCitations, data],
                });
              } else if (data.title !== undefined) {
                // Title event - update thread name
                const { threads, currentThread } = get();
                if (currentThread) {
                  set({
                    currentThread: { ...currentThread, name: data.title },
                    threads: threads.map((t) =>
                      t.id === currentThread.id ? { ...t, name: data.title } : t
                    ),
                  });
                }
              }
            } catch {
              // Ignore parse errors for incomplete chunks
            }
          }
        }

        // Exit loop after processing final data
        if (done) break;
      }

      // Always reset isSending after stream ends (handles cases where done event wasn't received)
      const { isSending } = get();
      if (isSending) {
        set({
          isSending: false,
          streamStatus: null,
        });
      }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to send message",
        isSending: false,
        streamStatus: null,
      });
    }
  },

  clearStreamingState: () => {
    set({
      streamStatus: null,
      streamingContent: "",
      streamingCitations: [],
    });
  },
}));
