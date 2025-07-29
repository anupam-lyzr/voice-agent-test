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
  Calendar,
  RefreshCw,
  PlayCircle,
  AlertTriangle,
  Server,
} from "lucide-react";

// Interfaces based on the backend API file (dashboard.py)
interface CampaignStats {
  total_clients: number;
  completed_calls: number;
  interested_clients: number;
  scheduled_meetings: number;
  completion_rate: number;
  interest_rate: number;
}

interface RecentActivity {
  id: string;
  timestamp: string;
  client_name: string;
  status: string;
  outcome: string | null;
}

interface SystemHealth {
  database: string;
  redis: string;
  twilio: string;
  lyzr: string;
  elevenlabs: string;
}

const API_BASE_URL = "http://localhost:8000/api/dashboard";

export default function Dashboard() {
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [activities, setActivities] = useState<RecentActivity[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [statsRes, activityRes, healthRes] = await Promise.all([
        fetch(`${API_BASE_URL}/stats`),
        fetch(`${API_BASE_URL}/recent-activity?limit=5`),
        fetch("http://localhost:8000/health"), // Assuming health check is at root
      ]);

      setStats(await statsRes.json());
      const activityData = await activityRes.json();
      setActivities(activityData.activities || []);
      const healthData = await healthRes.json();
      setHealth(healthData.components || null);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const getStatusBadge = (status: string) => {
    const s = status?.toLowerCase();
    if (s === "connected" || s === "healthy" || s === "completed") {
      return (
        <Badge variant="default" className="bg-green-100 text-green-800">
          {status}
        </Badge>
      );
    }
    if (s === "disconnected" || s === "unhealthy" || s === "failed") {
      return <Badge variant="destructive">{status}</Badge>;
    }
    return <Badge variant="secondary">{status}</Badge>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            Campaign Dashboard
          </h1>
          <p className="text-muted-foreground mt-1">
            Real-time analytics for the client re-engagement campaign.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            disabled={isLoading}
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button size="sm">
            <PlayCircle className="h-4 w-4 mr-2" />
            Manage Campaign
          </Button>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Clients</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.total_clients.toLocaleString() ?? "..."}
            </div>
            <p className="text-xs text-muted-foreground">
              Target for this campaign
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Calls Completed
            </CardTitle>
            <Phone className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.completed_calls.toLocaleString() ?? "..."}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats?.completion_rate.toFixed(1) ?? "0.0"}% of total
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Interested Leads
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats?.interested_clients.toLocaleString() ?? "..."}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats?.interest_rate.toFixed(1) ?? "0.0"}% conversion rate
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Meetings Scheduled
            </CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {stats?.scheduled_meetings.toLocaleString() ?? "..."}
            </div>
            <p className="text-xs text-muted-foreground">
              From interested leads
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>
              The latest 5 calls from the campaign.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Client</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activities.map((act) => (
                  <TableRow key={act.id}>
                    <TableCell className="font-medium">
                      {act.client_name}
                    </TableCell>
                    <TableCell>{act.outcome ?? "N/A"}</TableCell>
                    <TableCell>{getStatusBadge(act.status)}</TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground">
                      {new Date(act.timestamp).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" /> System Health
            </CardTitle>
            <CardDescription>Status of integrated services.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {health ? (
              Object.entries(health).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-sm font-medium capitalize">{key}</span>
                  {getStatusBadge(value)}
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">
                Could not load system health.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
