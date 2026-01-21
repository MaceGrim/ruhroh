import { useEffect, useCallback, useState } from "react";
import {
  Upload,
  FileText,
  Trash2,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
} from "lucide-react";
import { useDocumentsStore } from "@/stores";
import type { DocumentStatus } from "@/types";

const statusConfig: Record<
  DocumentStatus,
  { icon: React.ComponentType<{ className?: string }>; color: string; label: string }
> = {
  pending: { icon: Clock, color: "text-yellow-500", label: "Pending" },
  processing: { icon: Loader2, color: "text-blue-500", label: "Processing" },
  ready: { icon: CheckCircle, color: "text-green-500", label: "Ready" },
  failed: { icon: XCircle, color: "text-red-500", label: "Failed" },
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

export function DocumentsPage() {
  const { documents, isLoading, error, fetchDocuments, uploadDocument, deleteDocument } =
    useDocumentsStore();
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Poll for document status updates
  useEffect(() => {
    const processingDocs = documents.filter(
      (d) => d.status === "pending" || d.status === "processing"
    );

    if (processingDocs.length > 0) {
      const interval = setInterval(() => {
        fetchDocuments();
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [documents, fetchDocuments]);

  const handleFileUpload = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;

      setUploadError(null);
      setIsUploading(true);

      try {
        for (const file of Array.from(files)) {
          await uploadDocument(file);
        }
      } catch (err) {
        setUploadError(
          err instanceof Error ? err.message : "Failed to upload file"
        );
      } finally {
        setIsUploading(false);
      }
    },
    [uploadDocument]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      handleFileUpload(e.dataTransfer.files);
    },
    [handleFileUpload]
  );

  const handleDeleteDocument = async (id: string) => {
    if (confirm("Are you sure you want to delete this document?")) {
      try {
        await deleteDocument(id);
      } catch (err) {
        setUploadError(
          err instanceof Error ? err.message : "Failed to delete document"
        );
      }
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Documents
        </h1>
      </div>

      {/* Upload area */}
      <div
        className={`mb-8 border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
          isDragging
            ? "border-primary bg-primary/5"
            : "border-gray-300 dark:border-gray-600 hover:border-primary"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex flex-col items-center">
          <div className="w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-4">
            {isUploading ? (
              <Loader2 className="w-6 h-6 text-primary animate-spin" />
            ) : (
              <Upload className="w-6 h-6 text-gray-500" />
            )}
          </div>
          <p className="text-gray-700 dark:text-gray-300 mb-2">
            {isUploading
              ? "Uploading..."
              : "Drag and drop files here, or click to select"}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Supports PDF, DOCX, TXT, MD (max 50MB)
          </p>
          <label className="cursor-pointer">
            <span className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors">
              Select Files
            </span>
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              onChange={(e) => handleFileUpload(e.target.files)}
              disabled={isUploading}
            />
          </label>
        </div>
      </div>

      {/* Error message */}
      {(error || uploadError) && (
        <div className="mb-4 p-4 rounded-lg bg-error/10 text-error">
          {error || uploadError}
        </div>
      )}

      {/* Document list */}
      {isLoading && documents.length === 0 ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 text-primary animate-spin" />
        </div>
      ) : documents.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-500 dark:text-gray-400">
            No documents yet. Upload some to get started.
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Document
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Size
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Chunks
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {documents.map((doc) => {
                const status = statusConfig[doc.status];
                const StatusIcon = status.icon;

                return (
                  <tr
                    key={doc.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <FileText className="w-5 h-5 text-gray-400 mr-3" />
                        <div>
                          <div className="text-sm font-medium text-gray-900 dark:text-white">
                            {doc.filename}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {doc.content_type}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {formatBytes(doc.size_bytes)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1.5 text-sm ${status.color}`}
                      >
                        <StatusIcon
                          className={`w-4 h-4 ${
                            doc.status === "processing" ? "animate-spin" : ""
                          }`}
                        />
                        {status.label}
                      </span>
                      {doc.error_message && (
                        <p className="text-xs text-red-500 mt-1">
                          {doc.error_message}
                        </p>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {doc.chunk_count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <button
                        onClick={() => handleDeleteDocument(doc.id)}
                        className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                        title="Delete document"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
