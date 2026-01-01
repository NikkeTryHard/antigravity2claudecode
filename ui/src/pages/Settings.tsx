import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Check,
  Moon,
  Save,
  Server,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type ServerConfig } from "@/lib/api";

export function Settings() {
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    // Check initial dark mode state
    setDarkMode(document.documentElement.classList.contains("dark"));

    const fetchConfig = async () => {
      try {
        const data = await api.get<ServerConfig>("/admin/config");
        setConfig(data);
      } catch (error) {
        console.error("Failed to fetch config:", error);
        // Use mock data
        setConfig({
          server: {
            host: "127.0.0.1",
            port: 8080,
            log_level: "INFO",
            debug_enabled: true,
            metrics_enabled: true,
          },
          routing: {
            long_context_threshold: 100000,
            default_provider: "anthropic",
            background_provider: "antigravity",
            think_provider: "antigravity",
            long_context_provider: "gemini",
            websearch_provider: "gemini",
          },
          providers: {
            anthropic: {
              configured: true,
              base_url: "https://api.anthropic.com",
            },
            google: { configured: true },
            openai: {
              configured: false,
              base_url: "https://api.openai.com/v1",
            },
          },
        });
      } finally {
        setLoading(false);
      }
    };

    fetchConfig();
  }, []);

  const toggleDarkMode = () => {
    const html = document.documentElement;
    if (html.classList.contains("dark")) {
      html.classList.remove("dark");
      setDarkMode(false);
    } else {
      html.classList.add("dark");
      setDarkMode(true);
    }
  };

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-8 w-32" />
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-48" />
        ))}
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Configure your a2c instance
          </p>
        </div>
        <Button size="sm">
          <Save className="w-4 h-4 mr-2" />
          Save Changes
        </Button>
      </div>

      {/* Appearance */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {darkMode ? (
                <Moon className="w-5 h-5" />
              ) : (
                <Sun className="w-5 h-5" />
              )}
              Appearance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Dark Mode</p>
                <p className="text-sm text-muted-foreground">
                  Toggle dark theme
                </p>
              </div>
              <Switch checked={darkMode} onCheckedChange={toggleDarkMode} />
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Server settings */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="w-5 h-5" />
              Server Configuration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <p className="text-sm text-muted-foreground">Host</p>
                <p className="font-mono">{config?.server.host}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Port</p>
                <p className="font-mono">{config?.server.port}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Log Level</p>
                <Badge variant="outline">{config?.server.log_level}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Debug Mode</p>
                </div>
                <Switch checked={config?.server.debug_enabled} disabled />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Metrics</p>
                </div>
                <Switch checked={config?.server.metrics_enabled} disabled />
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Routing settings */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <SettingsIcon className="w-5 h-5" />
              Routing Configuration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <p className="text-sm text-muted-foreground">
                  Default Provider
                </p>
                <Badge className="capitalize">
                  {config?.routing.default_provider}
                </Badge>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Background Provider
                </p>
                <Badge variant="outline" className="capitalize">
                  {config?.routing.background_provider}
                </Badge>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Think Provider</p>
                <Badge variant="outline" className="capitalize">
                  {config?.routing.think_provider}
                </Badge>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Long Context Provider
                </p>
                <Badge variant="outline" className="capitalize">
                  {config?.routing.long_context_provider}
                </Badge>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Long Context Threshold
                </p>
                <p className="font-mono">
                  {config?.routing.long_context_threshold.toLocaleString()}{" "}
                  tokens
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Provider credentials */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card>
          <CardHeader>
            <CardTitle>Provider Credentials</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {config?.providers &&
                Object.entries(config.providers).map(([name, info]) => (
                  <div
                    key={name}
                    className="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-3 h-3 rounded-full ${
                          info.configured ? "bg-green-500" : "bg-gray-300"
                        }`}
                      />
                      <span className="font-medium capitalize">{name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {info.configured ? (
                        <Badge variant="default">
                          <Check className="w-3 h-3 mr-1" />
                          Configured
                        </Badge>
                      ) : (
                        <Badge variant="secondary">Not Configured</Badge>
                      )}
                    </div>
                  </div>
                ))}
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              Provider credentials are managed via environment variables.
              Restart the server after making changes.
            </p>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
