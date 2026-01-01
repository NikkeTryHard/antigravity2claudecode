import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, CheckCircle, RefreshCw, Server } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type ProvidersResponse } from "@/lib/api";

const statusConfig = {
  healthy: { color: "bg-green-500", icon: CheckCircle, label: "Healthy" },
  degraded: { color: "bg-yellow-500", icon: AlertCircle, label: "Degraded" },
  unhealthy: { color: "bg-red-500", icon: AlertCircle, label: "Unhealthy" },
  unknown: { color: "bg-gray-500", icon: AlertCircle, label: "Unknown" },
};

export function Providers() {
  const [data, setData] = useState<ProvidersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchProviders = async () => {
    try {
      const result = await api.get<ProvidersResponse>("/health/providers");
      setData(result);
    } catch (err) {
      console.error("Failed to fetch providers:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchProviders();
  };

  useEffect(() => {
    fetchProviders();
    const interval = setInterval(fetchProviders, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Providers</h1>
          <p className="text-sm text-muted-foreground">
            Manage and monitor AI providers
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw
            className={`w-4 h-4 mr-2 ${refreshing ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total</p>
                <p className="text-2xl font-bold">{data?.total ?? 0}</p>
              </div>
              <Server className="w-8 h-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Healthy</p>
                <p className="text-2xl font-bold text-green-500">
                  {data?.healthy ?? 0}
                </p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Degraded</p>
                <p className="text-2xl font-bold text-yellow-500">
                  {data?.degraded ?? 0}
                </p>
              </div>
              <AlertCircle className="w-8 h-8 text-yellow-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Unhealthy</p>
                <p className="text-2xl font-bold text-red-500">
                  {data?.unhealthy ?? 0}
                </p>
              </div>
              <AlertCircle className="w-8 h-8 text-red-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Provider cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {data?.providers &&
          Object.entries(data.providers).map(([name, provider], index) => {
            const status = provider.health?.status ?? "unknown";
            const config = statusConfig[status];
            const StatusIcon = config.icon;

            return (
              <motion.div
                key={name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card className="relative overflow-hidden">
                  <div
                    className={`absolute top-0 left-0 w-1 h-full ${config.color}`}
                  />
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg capitalize">
                        {name}
                      </CardTitle>
                      <Badge
                        variant={status === "healthy" ? "default" : "secondary"}
                      >
                        <StatusIcon className="w-3 h-3 mr-1" />
                        {config.label}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Status info */}
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-muted-foreground">Configured</p>
                        <p className="font-medium">
                          {provider.configured ? "Yes" : "No"}
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Latency</p>
                        <p className="font-medium">
                          {provider.health?.latency_ms
                            ? `${provider.health.latency_ms.toFixed(0)}ms`
                            : "-"}
                        </p>
                      </div>
                    </div>

                    {/* Capabilities */}
                    <div>
                      <p className="text-sm text-muted-foreground mb-2">
                        Capabilities
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {provider.capabilities?.streaming && (
                          <Badge variant="outline" className="text-xs">
                            Streaming
                          </Badge>
                        )}
                        {provider.capabilities?.thinking && (
                          <Badge variant="outline" className="text-xs">
                            Thinking
                          </Badge>
                        )}
                        {provider.capabilities?.tools && (
                          <Badge variant="outline" className="text-xs">
                            Tools
                          </Badge>
                        )}
                        {provider.capabilities?.vision && (
                          <Badge variant="outline" className="text-xs">
                            Vision
                          </Badge>
                        )}
                      </div>
                    </div>

                    {/* Error */}
                    {provider.health?.error && (
                      <div className="p-2 bg-destructive/10 rounded-md">
                        <p className="text-xs text-destructive">
                          {provider.health.error}
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
      </div>
    </div>
  );
}
