import { useEffect, useState, useCallback } from "react";
import {
  Users,
  FileText,
  MessageSquare,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { api } from "@/services/api";
import type { AdminStats, HealthStatus } from "@/types";

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}

function StatCard({ title, value, icon: Icon, color }: StatCardProps) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
            {value}
          </p>
        </div>
        <div className={`w-12 h-12 rounded-xl ${color} flex items-center justify-center`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );
}

function HealthIndicator({
  label,
  status,
}: {
  label: string;
  status: "ok" | "error" | "degraded" | undefined;
}) {
  const config = {
    ok: { icon: CheckCircle, color: "text-green-500", label: "Healthy" },
    degraded: { icon: AlertCircle, color: "text-yellow-500", label: "Degraded" },
    error: { icon: XCircle, color: "text-red-500", label: "Error" },
  };

  const { icon: Icon, color, label: statusLabel } = config[status || "error"];

  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-200 dark:border-gray-700 last:border-0">
      <span className="text-gray-700 dark:text-gray-300">{label}</span>
      <span className={`flex items-center gap-2 ${color}`}>
        <Icon className="w-4 h-4" />
        {statusLabel}
      </span>
    </div>
  );
}

export function StatsPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [statsData, healthData] = await Promise.all([
        api.getAdminStats(),
        api.getHealth(),
      ]);
      setStats(statsData);
      setHealth(healthData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch stats");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-full">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          System Statistics
        </h1>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-lg bg-error/10 text-error">{error}</div>
      )}

      {stats && (
        <>
          {/* Stats grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatCard
              title="Total Users"
              value={stats.total_users}
              icon={Users}
              color="bg-blue-500"
            />
            <StatCard
              title="Active Today"
              value={stats.active_users_today}
              icon={Users}
              color="bg-green-500"
            />
            <StatCard
              title="Total Documents"
              value={stats.total_documents}
              icon={FileText}
              color="bg-purple-500"
            />
            <StatCard
              title="Queries Today"
              value={stats.total_queries_today}
              icon={MessageSquare}
              color="bg-orange-500"
            />
          </div>

          {/* Document status breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Documents by Status
              </h2>
              <div className="space-y-3">
                {Object.entries(stats.documents_by_status).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-3 h-3 rounded-full ${
                          status === "ready"
                            ? "bg-green-500"
                            : status === "processing"
                            ? "bg-blue-500"
                            : status === "pending"
                            ? "bg-yellow-500"
                            : "bg-red-500"
                        }`}
                      />
                      <span className="text-gray-700 dark:text-gray-300 capitalize">
                        {status}
                      </span>
                    </div>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* System health */}
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                System Health
              </h2>
              {health && (
                <div>
                  <HealthIndicator label="API" status={health.api} />
                  <HealthIndicator label="Database" status={health.database} />
                  <HealthIndicator label="Vector Store" status={health.qdrant} />
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
