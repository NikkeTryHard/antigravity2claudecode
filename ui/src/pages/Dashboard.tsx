import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";
import { Toaster, toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  RefreshCw,
  Activity,
  Server,
  Zap,
  Moon,
  Sun,
  TrendingUp,
  TrendingDown,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Cpu,
  Globe,
  Brain,
  Eye,
  Wrench,
  MessageSquare,
} from "lucide-react";

// Types
interface ProviderHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
  latency_ms: number | null;
  last_check: string;
  error: string | null;
}

interface Provider {
  name: string;
  display_name: string;
  api_format: string;
  supports_streaming: boolean;
  supports_thinking: boolean;
  supports_tools: boolean;
  supports_vision: boolean;
  max_context_tokens: number;
  is_configured: boolean;
  is_healthy: boolean;
  health: ProviderHealth;
}

interface RoutingRule {
  name: string;
  provider: string;
  priority: number;
}

interface DashboardData {
  providers: Record<string, Provider>;
  routing: {
    default_provider: string;
    rules: RoutingRule[];
    total_rules: number;
  };
  stats: {
    total_requests: number;
    requests_per_minute: number;
    avg_latency_ms: number;
    error_rate: number;
  };
}

interface ChartDataPoint {
  time: string;
  requests: number;
  latency: number;
  errors: number;
}

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
} as const;

const itemVariants = {
  hidden: { y: 20, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: {
      type: "spring" as const,
      stiffness: 100,
    },
  },
};

const pulseVariants = {
  pulse: {
    scale: [1, 1.05, 1],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut" as const,
    },
  },
};

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const variants = {
    healthy: { variant: "success" as const, icon: CheckCircle2 },
    degraded: { variant: "warning" as const, icon: AlertCircle },
    unhealthy: { variant: "destructive" as const, icon: XCircle },
    unknown: { variant: "outline" as const, icon: Clock },
  };

  const config = variants[status as keyof typeof variants] ?? variants.unknown;
  const Icon = config.icon;

  return (
    <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
      <Badge variant={config.variant} className="gap-1">
        <Icon className="h-3 w-3" />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    </motion.div>
  );
}

// Animated stat card
function StatCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
  trendValue,
}: {
  title: string;
  value: string | number;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  trend?: "up" | "down";
  trendValue?: string;
}) {
  return (
    <motion.div variants={itemVariants} whileHover={{ y: -4 }}>
      <Card className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent" />
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          <motion.div
            whileHover={{ rotate: 15 }}
            transition={{ type: "spring", stiffness: 300 }}
          >
            <Icon className="h-4 w-4 text-muted-foreground" />
          </motion.div>
        </CardHeader>
        <CardContent>
          <motion.div
            className="text-2xl font-bold"
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 200 }}
          >
            {value}
          </motion.div>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-xs text-muted-foreground">{description}</p>
            {trend && trendValue && (
              <motion.span
                className={`flex items-center text-xs ${
                  trend === "up" ? "text-green-500" : "text-red-500"
                }`}
                initial={{ x: -10, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
              >
                {trend === "up" ? (
                  <TrendingUp className="h-3 w-3 mr-1" />
                ) : (
                  <TrendingDown className="h-3 w-3 mr-1" />
                )}
                {trendValue}
              </motion.span>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// Provider card with animations
function ProviderCard({ provider }: { provider: Provider }) {
  const capabilities = [
    { key: "streaming", icon: MessageSquare, label: "Streaming" },
    { key: "thinking", icon: Brain, label: "Thinking" },
    { key: "tools", icon: Wrench, label: "Tools" },
    { key: "vision", icon: Eye, label: "Vision" },
  ];

  return (
    <motion.div
      variants={itemVariants}
      whileHover={{ y: -4, boxShadow: "0 10px 40px -10px rgba(0,0,0,0.2)" }}
      transition={{ type: "spring", stiffness: 300 }}
    >
      <Card className="relative overflow-hidden h-full">
        <motion.div
          className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-primary/10 to-transparent rounded-full -translate-y-16 translate-x-16"
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <motion.div
                className={`w-2 h-2 rounded-full ${
                  provider.health.status === "healthy"
                    ? "bg-green-500"
                    : provider.health.status === "degraded"
                      ? "bg-yellow-500"
                      : "bg-red-500"
                }`}
                variants={pulseVariants}
                animate="pulse"
              />
              <CardTitle className="text-lg">{provider.display_name}</CardTitle>
            </div>
            <StatusBadge status={provider.health.status} />
          </div>
          <CardDescription className="flex items-center gap-1">
            <Globe className="h-3 w-3" />
            {provider.api_format.toUpperCase()} API
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Configured</span>
                <span
                  className={
                    provider.is_configured ? "text-green-500" : "text-red-500"
                  }
                >
                  {provider.is_configured ? "Yes" : "No"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Latency</span>
                <span>
                  {provider.health.latency_ms
                    ? `${provider.health.latency_ms.toFixed(0)}ms`
                    : "N/A"}
                </span>
              </div>
              <div className="flex justify-between col-span-2">
                <span className="text-muted-foreground">Context Window</span>
                <span className="font-mono">
                  {(provider.max_context_tokens / 1000).toFixed(0)}K tokens
                </span>
              </div>
            </div>

            <div className="pt-2 border-t">
              <p className="text-xs text-muted-foreground mb-2">Capabilities</p>
              <div className="flex flex-wrap gap-1">
                {capabilities.map(({ key, icon: CapIcon, label }) => {
                  const isSupported =
                    provider[`supports_${key}` as keyof Provider];
                  return (
                    <TooltipProvider key={key}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <motion.div
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                          >
                            <Badge
                              variant={isSupported ? "secondary" : "outline"}
                              className={`text-xs gap-1 ${
                                !isSupported && "opacity-40"
                              }`}
                            >
                              <CapIcon className="h-3 w-3" />
                              {label}
                            </Badge>
                          </motion.div>
                        </TooltipTrigger>
                        <TooltipContent>
                          {isSupported
                            ? `${label} supported`
                            : `${label} not supported`}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  );
                })}
              </div>
            </div>

            {provider.health.latency_ms && (
              <div className="pt-2">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Response Time</span>
                  <span>{provider.health.latency_ms.toFixed(0)}ms</span>
                </div>
                <Progress
                  value={Math.min(
                    100,
                    (provider.health.latency_ms / 500) * 100,
                  )}
                  className="h-1"
                />
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// Loading skeleton
function DashboardSkeleton() {
  return (
    <div className="container mx-auto py-8 px-4">
      <div className="flex items-center justify-between mb-8">
        <div>
          <Skeleton className="h-8 w-48 mb-2" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-10 w-24" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-8">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-64" />
        ))}
      </div>
    </div>
  );
}

// Generate mock chart data
function generateChartData(): ChartDataPoint[] {
  const data: ChartDataPoint[] = [];
  const now = new Date();
  for (let i = 23; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 60 * 60 * 1000);
    data.push({
      time: time.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
      }),
      requests: Math.floor(Math.random() * 100) + 50,
      latency: Math.floor(Math.random() * 200) + 100,
      errors: Math.floor(Math.random() * 5),
    });
  }
  return data;
}

// Main Dashboard component
export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [chartData] = useState<ChartDataPoint[]>(generateChartData);
  const [initialLoad, setInitialLoad] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/dashboard");
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const json = (await response.json()) as DashboardData;
      setData(json);
      toast.success("Dashboard updated", {
        description: "Latest data loaded successfully",
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch data";
      toast.error("Failed to update", {
        description: errorMessage,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  // Only fetch data when explicitly requested (Refresh button)
  // In production, uncomment to enable auto-refresh:
  // useEffect(() => {
  //   void fetchData();
  //   const interval = setInterval(() => void fetchData(), 30000);
  //   return () => clearInterval(interval);
  // }, [fetchData]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
  }, [darkMode]);

  // Mock data for development
  const mockData: DashboardData = data ?? {
    providers: {
      anthropic: {
        name: "anthropic",
        display_name: "Anthropic",
        api_format: "anthropic",
        supports_streaming: true,
        supports_thinking: true,
        supports_tools: true,
        supports_vision: true,
        max_context_tokens: 200000,
        is_configured: true,
        is_healthy: true,
        health: {
          status: "healthy",
          latency_ms: 150,
          last_check: new Date().toISOString(),
          error: null,
        },
      },
      gemini: {
        name: "gemini",
        display_name: "Google Gemini",
        api_format: "gemini",
        supports_streaming: true,
        supports_thinking: false,
        supports_tools: true,
        supports_vision: true,
        max_context_tokens: 1000000,
        is_configured: true,
        is_healthy: true,
        health: {
          status: "healthy",
          latency_ms: 200,
          last_check: new Date().toISOString(),
          error: null,
        },
      },
      openai: {
        name: "openai",
        display_name: "OpenAI",
        api_format: "openai",
        supports_streaming: true,
        supports_thinking: false,
        supports_tools: true,
        supports_vision: true,
        max_context_tokens: 128000,
        is_configured: false,
        is_healthy: false,
        health: {
          status: "unknown",
          latency_ms: null,
          last_check: new Date().toISOString(),
          error: "Not configured",
        },
      },
      antigravity: {
        name: "antigravity",
        display_name: "Antigravity",
        api_format: "anthropic",
        supports_streaming: true,
        supports_thinking: true,
        supports_tools: true,
        supports_vision: true,
        max_context_tokens: 200000,
        is_configured: true,
        is_healthy: true,
        health: {
          status: "degraded",
          latency_ms: 350,
          last_check: new Date().toISOString(),
          error: null,
        },
      },
    },
    routing: {
      default_provider: "anthropic",
      rules: [
        { name: "thinking-requests", provider: "antigravity", priority: 100 },
        { name: "long-context", provider: "gemini", priority: 90 },
        { name: "websearch", provider: "gemini", priority: 80 },
        { name: "background", provider: "antigravity", priority: 70 },
        { name: "think-agent", provider: "antigravity", priority: 60 },
        { name: "opus-models", provider: "antigravity", priority: 50 },
      ],
      total_rules: 6,
    },
    stats: {
      total_requests: 12847,
      requests_per_minute: 24.5,
      avg_latency_ms: 185,
      error_rate: 0.012,
    },
  };

  // Show skeleton only on initial load before first fetch attempt
  useEffect(() => {
    if (!loading) {
      setInitialLoad(false);
    }
  }, [loading]);

  if (initialLoad && loading) {
    return <DashboardSkeleton />;
  }

  return (
    <TooltipProvider>
      <Toaster richColors position="top-right" />
      <div className="min-h-screen bg-background transition-colors duration-300">
        <motion.div
          className="container mx-auto py-8 px-4"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {/* Header */}
          <motion.div
            className="flex items-center justify-between mb-8"
            variants={itemVariants}
          >
            <div>
              <motion.h1
                className="text-3xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent"
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
              >
                A2C Dashboard
              </motion.h1>
              <motion.p
                className="text-muted-foreground"
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ delay: 0.1 }}
              >
                Anthropic to Claude Code Proxy
              </motion.p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Sun className="h-4 w-4" />
                <Switch checked={darkMode} onCheckedChange={setDarkMode} />
                <Moon className="h-4 w-4" />
              </div>
              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Button
                  onClick={() => void fetchData()}
                  variant="outline"
                  disabled={loading}
                  className="gap-2"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
                  />
                  Refresh
                </Button>
              </motion.div>
            </div>
          </motion.div>

          {/* Stats Grid */}
          <motion.div
            className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8"
            variants={containerVariants}
          >
            <StatCard
              title="Total Requests"
              value={mockData.stats.total_requests.toLocaleString()}
              description="All time"
              icon={Activity}
              trend="up"
              trendValue="+12%"
            />
            <StatCard
              title="Requests/min"
              value={mockData.stats.requests_per_minute.toFixed(1)}
              description="Current rate"
              icon={Zap}
              trend="up"
              trendValue="+5%"
            />
            <StatCard
              title="Avg Latency"
              value={`${mockData.stats.avg_latency_ms.toFixed(0)}ms`}
              description="Last hour"
              icon={Clock}
              trend="down"
              trendValue="-8%"
            />
            <StatCard
              title="Error Rate"
              value={`${(mockData.stats.error_rate * 100).toFixed(2)}%`}
              description="Last hour"
              icon={Server}
              trend="down"
              trendValue="-2%"
            />
          </motion.div>

          {/* Charts */}
          <motion.div variants={itemVariants} className="mb-8">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="h-5 w-5" />
                  Performance Metrics
                </CardTitle>
                <CardDescription>
                  Request volume and latency over the last 24 hours
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="requests" className="w-full">
                  <TabsList className="mb-4">
                    <TabsTrigger value="requests">Requests</TabsTrigger>
                    <TabsTrigger value="latency">Latency</TabsTrigger>
                    <TabsTrigger value="errors">Errors</TabsTrigger>
                  </TabsList>
                  <TabsContent value="requests">
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                          <defs>
                            <linearGradient
                              id="colorRequests"
                              x1="0"
                              y1="0"
                              x2="0"
                              y2="1"
                            >
                              <stop
                                offset="5%"
                                stopColor="hsl(var(--primary))"
                                stopOpacity={0.3}
                              />
                              <stop
                                offset="95%"
                                stopColor="hsl(var(--primary))"
                                stopOpacity={0}
                              />
                            </linearGradient>
                          </defs>
                          <CartesianGrid
                            strokeDasharray="3 3"
                            className="stroke-muted"
                          />
                          <XAxis dataKey="time" className="text-xs" />
                          <YAxis className="text-xs" />
                          <RechartsTooltip
                            contentStyle={{
                              backgroundColor: "hsl(var(--card))",
                              border: "1px solid hsl(var(--border))",
                              borderRadius: "8px",
                            }}
                          />
                          <Area
                            type="monotone"
                            dataKey="requests"
                            stroke="hsl(var(--primary))"
                            fillOpacity={1}
                            fill="url(#colorRequests)"
                            strokeWidth={2}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </TabsContent>
                  <TabsContent value="latency">
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                          <CartesianGrid
                            strokeDasharray="3 3"
                            className="stroke-muted"
                          />
                          <XAxis dataKey="time" className="text-xs" />
                          <YAxis className="text-xs" />
                          <RechartsTooltip
                            contentStyle={{
                              backgroundColor: "hsl(var(--card))",
                              border: "1px solid hsl(var(--border))",
                              borderRadius: "8px",
                            }}
                          />
                          <Line
                            type="monotone"
                            dataKey="latency"
                            stroke="hsl(var(--chart-2))"
                            strokeWidth={2}
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </TabsContent>
                  <TabsContent value="errors">
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                          <defs>
                            <linearGradient
                              id="colorErrors"
                              x1="0"
                              y1="0"
                              x2="0"
                              y2="1"
                            >
                              <stop
                                offset="5%"
                                stopColor="hsl(var(--destructive))"
                                stopOpacity={0.3}
                              />
                              <stop
                                offset="95%"
                                stopColor="hsl(var(--destructive))"
                                stopOpacity={0}
                              />
                            </linearGradient>
                          </defs>
                          <CartesianGrid
                            strokeDasharray="3 3"
                            className="stroke-muted"
                          />
                          <XAxis dataKey="time" className="text-xs" />
                          <YAxis className="text-xs" />
                          <RechartsTooltip
                            contentStyle={{
                              backgroundColor: "hsl(var(--card))",
                              border: "1px solid hsl(var(--border))",
                              borderRadius: "8px",
                            }}
                          />
                          <Area
                            type="monotone"
                            dataKey="errors"
                            stroke="hsl(var(--destructive))"
                            fillOpacity={1}
                            fill="url(#colorErrors)"
                            strokeWidth={2}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </motion.div>

          {/* Providers Grid */}
          <motion.div variants={itemVariants} className="mb-8">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <Server className="h-5 w-5" />
              Providers
            </h2>
            <motion.div
              className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
              variants={containerVariants}
            >
              <AnimatePresence>
                {Object.values(mockData.providers).map((provider) => (
                  <ProviderCard key={provider.name} provider={provider} />
                ))}
              </AnimatePresence>
            </motion.div>
          </motion.div>

          {/* Routing Rules */}
          <motion.div variants={itemVariants}>
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Routing Rules
            </h2>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Active Rules</CardTitle>
                <CardDescription>
                  Default provider:{" "}
                  <Badge variant="outline">
                    {mockData.routing.default_provider}
                  </Badge>
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <AnimatePresence>
                    {mockData.routing.rules.map((rule, index) => (
                      <motion.div
                        key={rule.name}
                        initial={{ x: -20, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: 20, opacity: 0 }}
                        transition={{ delay: index * 0.05 }}
                        whileHover={{ x: 4 }}
                        className="flex items-center justify-between py-3 px-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <Badge
                            variant="secondary"
                            className="font-mono text-xs w-8 justify-center"
                          >
                            {rule.priority}
                          </Badge>
                          <span className="font-medium">{rule.name}</span>
                        </div>
                        <Badge variant="outline">{rule.provider}</Badge>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>
      </div>
    </TooltipProvider>
  );
}
