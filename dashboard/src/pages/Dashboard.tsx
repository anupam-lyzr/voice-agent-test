import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Progress } from "../components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  Users,
  Phone,
  CheckCircle,
  TrendingUp,
  Activity,
  RefreshCw,
  Server,
} from "lucide-react";
import { toast } from "sonner";

interface CampaignStats {
  total_clients: number;
  completed_calls: number;
  interested_clients: number;
  not_interested_clients: number;
  pending_clients: number;
  completion_rate: number;
  interest_rate: number;
  last_updated: string;
}

interface CallLog {
  call_id: string;
  client_name: string;
  client_phone: string;
  outcome: string;
  duration: string;
  started_at: string;
}

interface SystemHealth {
  status: string;
  components: {
    database: { connected: boolean };
    cache: { connected: boolean };
    voice_processor: { configured: boolean };
    hybrid_tts: { configured: boolean };
  };
}

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL + "/api/dashboard" ||
  "http://localhost:8000/api/dashboard";

export default function Dashboard() {
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [callLogs, setCallLogs] = useState<CallLog[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [statsRes, callLogsRes, healthRes] = await Promise.all([
        fetch(`${API_BASE_URL}/stats`),
        fetch(`${API_BASE_URL}/call-logs?limit=10`),
        fetch(`${API_BASE_URL}/system-health`),
      ]);

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      if (callLogsRes.ok) {
        const logsData = await callLogsRes.json();
        setCallLogs(logsData.logs || []);
      }

      if (healthRes.ok) {
        const healthData = await healthRes.json();
        setHealth(healthData);
      }

      setLastRefresh(new Date());
      toast.success("Dashboard data refreshed");
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
      toast.error("Failed to refresh dashboard data");
    } finally {
      setIsLoading(false);
    }
  };

  const refreshSystemHealth = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/system-health/refresh`, {
        method: "POST",
      });
      if (response.ok) {
        const healthData = await response.json();
        setHealth(healthData);
        setLastRefresh(new Date());
        toast.success("System health refreshed");
      } else {
        toast.error("Failed to refresh system health");
      }
    } catch (error) {
      console.error("Failed to refresh system health:", error);
      toast.error("Failed to refresh system health");
    }
  };

  useEffect(() => {
    fetchData();
    // Removed automatic polling - now only manual refresh
    // const interval = setInterval(fetchData, 30000);
    // return () => clearInterval(interval);
  }, []);

  const getStatusBadge = (status: string) => {
    const statusMap = {
      healthy: { variant: "default" as const, color: "text-green-600" },
      degraded: { variant: "secondary" as const, color: "text-yellow-600" },
      unhealthy: { variant: "destructive" as const, color: "text-red-600" },
    };
    return statusMap[status as keyof typeof statusMap] || statusMap.unhealthy;
  };

  const getOutcomeBadge = (outcome: string) => {
    const outcomeMap = {
      interested: { variant: "default" as const, color: "text-green-600" },
      not_interested: { variant: "secondary" as const, color: "text-gray-600" },
      dnc_requested: { variant: "destructive" as const, color: "text-red-600" },
      no_answer: { variant: "outline" as const, color: "text-yellow-600" },
    };
    return (
      outcomeMap[outcome as keyof typeof outcomeMap] || {
        variant: "outline" as const,
        color: "text-gray-600",
      }
    );
  };

  if (isLoading && !stats) {
    return (
      <div className="p-8">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <span className="ml-2">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Voice Agent Dashboard
          </h1>
          <p className="text-muted-foreground">
            Production campaign monitoring and testing interface
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <Badge variant="outline" className="text-xs">
            Last updated: {lastRefresh.toLocaleTimeString()}
          </Badge>
          <Button
            onClick={fetchData}
            disabled={isLoading}
            size="sm"
            variant="outline"
          >
            <RefreshCw
              className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            <span className="ml-2">Refresh</span>
          </Button>
        </div>
      </div>

      {health && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center">
                <Server className="h-5 w-5 mr-2" />
                System Health
              </div>
              <Button
                onClick={refreshSystemHealth}
                disabled={isLoading}
                size="sm"
                variant="outline"
              >
                <RefreshCw
                  className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
                />
                <span className="ml-2">Refresh Health</span>
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-4">
              <Badge {...getStatusBadge(health.status)}>
                {health.status.toUpperCase()}
              </Badge>
              <span className="text-sm text-muted-foreground">
                Components: Database {health.components?.database ? "✓" : "✗"},
                Cache {health.components?.cache ? "✓" : "✗"}, Voice{" "}
                {health.components?.voice_processor ? "✓" : "✗"}
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Total Clients
              </CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.total_clients.toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats.pending_clients.toLocaleString()} pending
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Completed Calls
              </CardTitle>
              <Phone className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.completed_calls.toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats.completion_rate.toFixed(1)}% completion rate
              </p>
              <Progress value={stats.completion_rate} className="mt-2" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Interested Clients
              </CardTitle>
              <CheckCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {stats.interested_clients.toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats.interest_rate.toFixed(1)}% interest rate
              </p>
              <Progress value={stats.interest_rate} className="mt-2" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Not Interested
              </CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.not_interested_clients.toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground">
                Campaign responses
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Activity className="h-5 w-5 mr-2" />
            Recent Call Activity
          </CardTitle>
          <CardDescription>Latest call outcomes and summaries</CardDescription>
        </CardHeader>
        <CardContent>
          {callLogs.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Call ID</TableHead>
                  <TableHead>Client</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {callLogs.map((log) => (
                  <TableRow key={log.call_id}>
                    <TableCell className="font-medium">
                      {log.call_id.substring(0, 8)}...
                    </TableCell>
                    <TableCell>{log.client_name || log.client_phone}</TableCell>
                    <TableCell>
                      <Badge {...getOutcomeBadge(log.outcome)}>
                        {log.outcome.replace("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell>{log.duration}</TableCell>
                    <TableCell>
                      {new Date(log.started_at).toLocaleTimeString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No recent call activity found
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
