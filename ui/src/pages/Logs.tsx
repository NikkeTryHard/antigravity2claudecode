import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  AlertCircle,
  CheckCircle,
  Filter,
  Pause,
  Play,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DebugRequest, type DebugRequestsResponse } from "@/lib/api";
import {
  useRequestEvents,
  type RequestCompletedData,
  type RequestErrorData,
  type RequestStartedData,
} from "@/hooks/useWebSocket";

export function Logs() {
  const [logs, setLogs] = useState<DebugRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async () => {
    try {
      const data = await api.get<DebugRequestsResponse>(
        "/debug/requests?limit=50",
      );
      setLogs(data.items ?? []);
    } catch (error) {
      console.error("Failed to fetch logs:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  // WebSocket event handlers
  const handleRequestStarted = useCallback(
    (data: RequestStartedData) => {
      if (paused) return;

      // Add a new pending log entry at the top
      const newLog: DebugRequest = {
        id: data.request_id,
        request_id: data.request_id,
        created_at: new Date().toISOString(),
        completed_at: null,
        provider: data.provider,
        model: data.model,
        agent_type: data.agent_type,
        status_code: null,
        latency_ms: null,
        input_tokens: null,
        output_tokens: null,
        is_streaming: false,
        error: null,
      };

      setLogs((prev) => [newLog, ...prev.slice(0, 49)]);
    },
    [paused],
  );

  const handleRequestCompleted = useCallback(
    (data: RequestCompletedData) => {
      if (paused) return;

      setLogs((prev) =>
        prev.map((log) =>
          log.request_id === data.request_id
            ? {
                ...log,
                completed_at: new Date().toISOString(),
                status_code: data.status_code,
                latency_ms: data.latency_ms,
                input_tokens: data.input_tokens,
                output_tokens: data.output_tokens,
              }
            : log,
        ),
      );
    },
    [paused],
  );

  const handleRequestError = useCallback(
    (data: RequestErrorData) => {
      if (paused) return;

      setLogs((prev) =>
        prev.map((log) =>
          log.request_id === data.request_id
            ? {
                ...log,
                completed_at: new Date().toISOString(),
                status_code: 500,
                error: data.error,
              }
            : log,
        ),
      );
    },
    [paused],
  );

  // Use WebSocket for real-time updates
  const { isConnected } = useRequestEvents(
    handleRequestStarted,
    handleRequestCompleted,
    handleRequestError,
  );

  // Initial load
  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const filteredLogs = filter
    ? logs.filter((log) => log.provider === filter)
    : logs;

  const providers = [...new Set(logs.map((l) => l.provider))];

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-32" />
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Logs</h1>
          <p className="text-sm text-muted-foreground">
            Real-time request logs
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPaused(!paused)}
          >
            {paused ? (
              <>
                <Play className="w-4 h-4 mr-2" />
                Resume
              </>
            ) : (
              <>
                <Pause className="w-4 h-4 mr-2" />
                Pause
              </>
            )}
          </Button>
          <Button
            variant={filter ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter(null)}
          >
            <Filter className="w-4 h-4 mr-2" />
            {filter ?? "All"}
          </Button>
        </div>
      </div>

      {/* Provider filter */}
      {providers.length > 0 && (
        <div className="flex gap-2">
          {providers.map((provider) => (
            <Button
              key={provider}
              variant={filter === provider ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter(filter === provider ? null : provider)}
              className="capitalize"
            >
              {provider}
            </Button>
          ))}
        </div>
      )}

      {/* Logs list */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Activity className={`w-4 h-4 ${!paused ? "animate-pulse" : ""}`} />
            Live Logs
            {isConnected ? (
              <Badge variant="secondary" className="text-xs gap-1">
                <Wifi className="w-3 h-3" />
                Connected
              </Badge>
            ) : (
              <Badge variant="outline" className="text-xs gap-1">
                <WifiOff className="w-3 h-3" />
                Disconnected
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y max-h-[600px] overflow-auto">
            <AnimatePresence mode="popLayout">
              {filteredLogs.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  No logs to display
                </div>
              ) : (
                filteredLogs.map((log) => (
                  <motion.div
                    key={log.id}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="p-4 hover:bg-muted/50"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        {log.status_code && log.status_code < 300 ? (
                          <CheckCircle className="w-5 h-5 text-green-500" />
                        ) : (
                          <AlertCircle className="w-5 h-5 text-red-500" />
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm">
                              {log.request_id}
                            </span>
                            <Badge variant="outline" className="capitalize">
                              {log.provider}
                            </Badge>
                            {log.model && (
                              <Badge variant="secondary" className="text-xs">
                                {log.model}
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(log.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 text-sm">
                        <div>
                          <span
                            className={
                              log.status_code && log.status_code < 300
                                ? "text-green-500"
                                : "text-red-500"
                            }
                          >
                            {log.status_code ?? "-"}
                          </span>
                        </div>
                        <div className="text-muted-foreground">
                          {log.latency_ms ? `${log.latency_ms}ms` : "-"}
                        </div>
                      </div>
                    </div>
                    {log.error && (
                      <div className="mt-2 p-2 bg-destructive/10 rounded text-xs text-destructive">
                        {log.error}
                      </div>
                    )}
                  </motion.div>
                ))
              )}
            </AnimatePresence>
            <div ref={logsEndRef} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
