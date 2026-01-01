import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, GitBranch, Plus, Settings } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type RoutingConfig } from "@/lib/api";

export function Routing() {
  const [config, setConfig] = useState<RoutingConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const data = await api.get<RoutingConfig>("/admin/routing");
        setConfig(data);
      } catch (error) {
        console.error("Failed to fetch routing config:", error);
        // Use mock data if server not available
        setConfig({
          default_provider: "anthropic",
          long_context_threshold: 100000,
          rules: [
            {
              name: "background_agents",
              priority: 100,
              condition: "agent_type == 'background'",
              provider: "antigravity",
              enabled: true,
            },
            {
              name: "extended_thinking",
              priority: 90,
              condition: "thinking == true",
              provider: "antigravity",
              enabled: true,
            },
            {
              name: "long_context",
              priority: 80,
              condition: "tokens > 100000",
              provider: "gemini",
              enabled: true,
            },
          ],
        });
      } finally {
        setLoading(false);
      }
    };

    fetchConfig();
  }, []);

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Routing</h1>
          <p className="text-sm text-muted-foreground">
            Configure request routing rules
          </p>
        </div>
        <Button size="sm">
          <Plus className="w-4 h-4 mr-2" />
          Add Rule
        </Button>
      </div>

      {/* Default settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Default Settings
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <p className="text-sm text-muted-foreground">Default Provider</p>
              <p className="font-medium capitalize">
                {config?.default_provider}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">
                Long Context Threshold
              </p>
              <p className="font-medium">
                {config?.long_context_threshold?.toLocaleString()} tokens
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Active Rules</p>
              <p className="font-medium">
                {config?.rules?.filter((r) => r.enabled).length ?? 0}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Routing flow visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="w-5 h-5" />
            Routing Flow
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-primary/10 text-primary">
                <span className="text-sm font-medium">Request</span>
              </div>
              <ArrowRight className="w-5 h-5 text-muted-foreground" />
              <div className="p-3 rounded-lg bg-secondary">
                <span className="text-sm font-medium">Rules Engine</span>
              </div>
              <ArrowRight className="w-5 h-5 text-muted-foreground" />
              <div className="flex flex-col gap-2">
                {["anthropic", "antigravity", "gemini", "openai"].map(
                  (provider) => (
                    <div
                      key={provider}
                      className="p-2 rounded-lg bg-muted text-sm capitalize"
                    >
                      {provider}
                    </div>
                  ),
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Rules list */}
      <Card>
        <CardHeader>
          <CardTitle>Routing Rules</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {config?.rules?.map((rule, index) => (
              <motion.div
                key={rule.name}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-center justify-between p-4 border rounded-lg"
              >
                <div className="flex items-center gap-4">
                  <Badge variant="outline">{rule.priority}</Badge>
                  <div>
                    <p className="font-medium">{rule.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {rule.condition}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <ArrowRight className="w-4 h-4 text-muted-foreground" />
                    <Badge
                      variant={rule.enabled ? "default" : "secondary"}
                      className="capitalize"
                    >
                      {rule.provider}
                    </Badge>
                  </div>
                  <Button variant="ghost" size="sm">
                    Edit
                  </Button>
                </div>
              </motion.div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
