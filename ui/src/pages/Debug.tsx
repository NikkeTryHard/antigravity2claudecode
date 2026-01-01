import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Bug,
  ChevronDown,
  ChevronRight,
  Clock,
  Loader2,
  Play,
  RefreshCw,
  Search,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  api,
  type DebugRequest,
  type DebugRequestsResponse,
  type DebugStats,
} from "@/lib/api";

interface ReplayResult {
  original_request_id: string;
  new_request_id: string;
  status_code: number;
  latency_ms: number;
}

export function Debug() {
  const [requests, setRequests] = useState<DebugRequest[]>([]);
  const [stats, setStats] = useState<DebugStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedRequest, setSelectedRequest] = useState<DebugRequest | null>(
    null,
  );
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(["request"]),
  );
  const [replaying, setReplaying] = useState(false);
  const [replayResult, setReplayResult] = useState<ReplayResult | null>(null);

  const fetchData = async () => {
    try {
      const [requestsData, statsData] = await Promise.all([
        api.get<DebugRequestsResponse>("/debug/requests?limit=20"),
        api.get<DebugStats>("/debug/stats?hours=24"),
      ]);

      setRequests(requestsData.items ?? []);
      setStats(statsData);
    } catch (error) {
      console.error("Failed to fetch debug data:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchRequestDetails = async (requestId: string) => {
    try {
      const data = await api.get<DebugRequest>(`/debug/requests/${requestId}`);
      setSelectedRequest(data);
      setReplayResult(null);
    } catch (error) {
      console.error("Failed to fetch request details:", error);
    }
  };

  const replayRequest = async (requestId: string) => {
    setReplaying(true);
    setReplayResult(null);
    try {
      const result = await api.post<ReplayResult>(
        `/debug/requests/${requestId}/replay`,
      );
      setReplayResult(result);
      // Refresh the request list to include the new request
      fetchData();
    } catch (error) {
      console.error("Failed to replay request:", error);
    } finally {
      setReplaying(false);
    }
  };

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-8 w-32" />
        <div className="grid gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Debug</h1>
          <p className="text-sm text-muted-foreground">
            Inspect request/response data
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Requests (24h)</p>
              <p className="text-2xl font-bold">{stats.total_requests}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Errors</p>
              <p className="text-2xl font-bold text-red-500">
                {stats.total_errors}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Error Rate</p>
              <p className="text-2xl font-bold">
                {(stats.error_rate * 100).toFixed(1)}%
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Avg Latency</p>
              <p className="text-2xl font-bold">
                {stats.avg_latency_ms?.toFixed(0) ?? "-"}ms
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main content */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Request list */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bug className="w-5 h-5" />
              Recent Requests
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y max-h-[500px] overflow-auto">
              {requests.map((req, index) => (
                <motion.div
                  key={req.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: index * 0.05 }}
                  className={`p-4 cursor-pointer hover:bg-muted/50 ${
                    selectedRequest?.id === req.id ? "bg-muted" : ""
                  }`}
                  onClick={() => fetchRequestDetails(req.request_id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          req.status_code && req.status_code < 300
                            ? "default"
                            : "destructive"
                        }
                      >
                        {req.status_code ?? "-"}
                      </Badge>
                      <span className="font-mono text-sm truncate max-w-[200px]">
                        {req.request_id}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      {req.latency_ms}ms
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                    <Badge variant="outline" className="capitalize">
                      {req.provider}
                    </Badge>
                    {req.model && <span>{req.model}</span>}
                    {req.is_streaming && <Badge variant="secondary">SSE</Badge>}
                  </div>
                </motion.div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Request details */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="w-5 h-5" />
              Request Inspector
            </CardTitle>
          </CardHeader>
          <CardContent>
            {selectedRequest ? (
              <div className="space-y-4">
                {/* Metadata */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Request ID</p>
                    <p className="font-mono">{selectedRequest.request_id}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Provider</p>
                    <p className="capitalize">{selectedRequest.provider}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Status</p>
                    <Badge
                      variant={
                        selectedRequest.status_code &&
                        selectedRequest.status_code < 300
                          ? "default"
                          : "destructive"
                      }
                    >
                      {selectedRequest.status_code}
                    </Badge>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Latency</p>
                    <p>{selectedRequest.latency_ms}ms</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Tokens</p>
                    <p>
                      {selectedRequest.input_tokens ?? "-"} in /{" "}
                      {selectedRequest.output_tokens ?? "-"} out
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Streaming</p>
                    <p>{selectedRequest.is_streaming ? "Yes" : "No"}</p>
                  </div>
                </div>

                {/* Replay button */}
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => replayRequest(selectedRequest.request_id)}
                    disabled={replaying}
                  >
                    {replaying ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Replaying...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 mr-2" />
                        Replay Request
                      </>
                    )}
                  </Button>
                </div>

                {/* Replay result */}
                {replayResult && (
                  <div className="p-3 bg-primary/10 rounded-lg">
                    <p className="text-sm font-medium">Replay Completed</p>
                    <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                      <div>
                        <span className="text-muted-foreground">New ID:</span>{" "}
                        <span className="font-mono">
                          {replayResult.new_request_id}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Status:</span>{" "}
                        <Badge
                          variant={
                            replayResult.status_code < 300
                              ? "default"
                              : "destructive"
                          }
                          className="text-xs"
                        >
                          {replayResult.status_code}
                        </Badge>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Latency:</span>{" "}
                        {replayResult.latency_ms}ms
                      </div>
                    </div>
                  </div>
                )}

                {/* Collapsible sections */}
                <div className="space-y-2">
                  {/* Request body */}
                  <div className="border rounded-lg">
                    <button
                      className="w-full p-3 flex items-center justify-between hover:bg-muted/50"
                      onClick={() => toggleSection("request")}
                    >
                      <span className="font-medium">Request Body</span>
                      {expandedSections.has("request") ? (
                        <ChevronDown className="w-4 h-4" />
                      ) : (
                        <ChevronRight className="w-4 h-4" />
                      )}
                    </button>
                    {expandedSections.has("request") && (
                      <pre className="p-3 text-xs overflow-auto max-h-48 bg-muted/30">
                        {JSON.stringify(
                          selectedRequest.request_body,
                          null,
                          2,
                        ) ?? "No data"}
                      </pre>
                    )}
                  </div>

                  {/* Response body */}
                  <div className="border rounded-lg">
                    <button
                      className="w-full p-3 flex items-center justify-between hover:bg-muted/50"
                      onClick={() => toggleSection("response")}
                    >
                      <span className="font-medium">Response Body</span>
                      {expandedSections.has("response") ? (
                        <ChevronDown className="w-4 h-4" />
                      ) : (
                        <ChevronRight className="w-4 h-4" />
                      )}
                    </button>
                    {expandedSections.has("response") && (
                      <pre className="p-3 text-xs overflow-auto max-h-48 bg-muted/30">
                        {JSON.stringify(
                          selectedRequest.response_body,
                          null,
                          2,
                        ) ?? "No data"}
                      </pre>
                    )}
                  </div>
                </div>

                {/* Error */}
                {selectedRequest.error && (
                  <div className="p-3 bg-destructive/10 rounded-lg">
                    <p className="text-sm font-medium text-destructive">
                      Error
                    </p>
                    <p className="text-xs text-destructive mt-1">
                      {selectedRequest.error}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <ArrowRight className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Select a request to inspect</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
