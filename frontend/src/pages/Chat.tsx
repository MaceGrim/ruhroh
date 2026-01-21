import { useEffect, useState, useRef } from "react";
import {
  Send,
  Plus,
  MessageSquare,
  Trash2,
  Loader2,
  FileText,
  Search,
  Sparkles,
} from "lucide-react";
import { useChatStore } from "@/stores";
import type { Citation, Message, SSEStatus } from "@/types";

const statusMessages: Record<SSEStatus, string> = {
  searching: "Searching documents...",
  thinking: "Analyzing context...",
  generating: "Generating response...",
};

function CitationBadge({ citation }: { citation: Citation }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <span
        className="inline-flex items-center justify-center w-5 h-5 text-xs font-medium bg-primary/10 text-primary rounded hover:bg-primary/20 transition-colors cursor-help"
      >
        {citation.index}
      </span>
      {isOpen && (
        <div className="absolute z-10 bottom-full left-0 mb-2 w-72 p-3 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-start gap-2 mb-2">
            <FileText className="w-4 h-4 text-gray-400 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {citation.document_name}
              </p>
              {citation.pages && citation.pages.length > 0 && (
                <p className="text-xs text-gray-500">
                  Page{citation.pages.length > 1 ? "s" : ""}: {citation.pages.join(", ")}
                </p>
              )}
            </div>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-300 line-clamp-4">
            {citation.excerpt}
          </p>
        </div>
      )}
    </span>
  );
}

function MessageContent({
  content,
  citations,
}: {
  content: string;
  citations: Citation[] | null;
}) {
  // Parse content and replace citation markers with interactive badges
  if (!citations || citations.length === 0) {
    return <div className="whitespace-pre-wrap">{content}</div>;
  }

  const citationMap = new Map(citations.map((c) => [c.index, c]));
  const parts = content.split(/(\[\d+\])/g);

  return (
    <div className="whitespace-pre-wrap">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const index = parseInt(match[1], 10);
          const citation = citationMap.get(index);
          if (citation) {
            return <CitationBadge key={i} citation={citation} />;
          }
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}

function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-primary text-white"
            : "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
        }`}
      >
        <MessageContent content={message.content} citations={message.citations} />
        {message.is_from_documents && !isUser && (
          <div className="flex items-center gap-1 mt-2 text-xs text-gray-500 dark:text-gray-400">
            <FileText className="w-3 h-3" />
            Based on your documents
          </div>
        )}
      </div>
    </div>
  );
}

function StreamingMessage({
  content,
  citations,
  status,
}: {
  content: string;
  citations: Citation[];
  status: SSEStatus | null;
}) {
  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
        {status && !content && (
          <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
            {status === "searching" && <Search className="w-4 h-4 animate-pulse" />}
            {status === "thinking" && <Sparkles className="w-4 h-4 animate-pulse" />}
            {status === "generating" && <Loader2 className="w-4 h-4 animate-spin" />}
            <span className="text-sm">{statusMessages[status]}</span>
          </div>
        )}
        {content && (
          <MessageContent
            content={content}
            citations={citations.length > 0 ? citations : null}
          />
        )}
      </div>
    </div>
  );
}

export function ChatPage() {
  const {
    threads,
    currentThread,
    isLoadingThreads,
    isSending,
    streamStatus,
    streamingContent,
    streamingCitations,
    fetchThreads,
    selectThread,
    createThread,
    deleteThread,
    sendMessage,
  } = useChatStore();

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentThread?.messages, streamingContent]);

  const handleSend = async () => {
    if (!input.trim() || isSending) return;

    // Create thread if none exists
    if (!currentThread) {
      await createThread();
    }

    const message = input;
    setInput("");
    await sendMessage(message);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = async () => {
    await createThread();
  };

  const handleDeleteThread = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Delete this conversation?")) {
      await deleteThread(id);
    }
  };

  return (
    <div className="flex h-full">
      {/* Thread sidebar */}
      <div className="w-64 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoadingThreads ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
            </div>
          ) : threads.length === 0 ? (
            <div className="p-4 text-center text-gray-500 dark:text-gray-400">
              No conversations yet
            </div>
          ) : (
            <ul className="p-2 space-y-1">
              {threads.map((thread) => (
                <li key={thread.id}>
                  <div
                    onClick={() => selectThread(thread.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors group cursor-pointer ${
                      currentThread?.id === thread.id
                        ? "bg-primary/10 text-primary"
                        : "hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <MessageSquare className="w-4 h-4 flex-shrink-0" />
                      <span className="truncate text-sm">{thread.name}</span>
                    </div>
                    <button
                      onClick={(e) => handleDeleteThread(thread.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-all"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col bg-gray-50 dark:bg-gray-900">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6">
          {!currentThread ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <MessageSquare className="w-8 h-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                Start a conversation
              </h2>
              <p className="text-gray-500 dark:text-gray-400 max-w-md">
                Ask questions about your documents and get answers with citations.
              </p>
            </div>
          ) : (
            <>
              {currentThread.messages?.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              {isSending && (
                <StreamingMessage
                  content={streamingContent}
                  citations={streamingCitations}
                  status={streamStatus}
                />
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
          <div className="max-w-4xl mx-auto flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your documents..."
              className="flex-1 resize-none px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent dark:bg-gray-700 dark:text-white"
              rows={1}
              disabled={isSending}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isSending}
              className="px-4 py-3 bg-primary text-white rounded-xl hover:bg-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
