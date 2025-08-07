import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { Progress } from "../components/ui/progress";
import {
  Phone,
  User,
  Play,
  Loader2,
  Clock,
  RefreshCw,
  Rocket,
  PlusCircle,
  Eye,
  Trash2,
  PhoneCall,
  Activity,
  TrendingUp,
  AlertTriangle,
  // Settings,
  Timer,
  Mic,
  Speaker,
  // Database,
  // Monitor,
  Zap,
  Users,
  Target,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface TestClient {
  id: string;
  name: string;
  phone: string;
  email?: string;
  status: string;
  total_attempts: number;
  created_at: string;
  last_call_outcome?: string;
}

interface TestAgent {
  id: string;
  name: string;
  email: string;
  timezone: string;
  specialties: string[];
  working_hours: string;
  google_calendar_id?: string;
}

interface CallLog {
  call_id: string;
  call_sid: string;
  client_name: string;
  client_phone: string;
  agent_name?: string;
  status: string;
  outcome: string;
  duration: string;
  started_at: string;
  completed_at?: string;
  summary?: string;
  is_test_call: boolean;
  conversation_turns?: number;
}

interface CallSummary {
  outcome: string;
  sentiment: string;
  key_points: string[];
  customer_concerns: string[];
  recommended_actions: string[];
  agent_notes: string;
  urgency: string;
  follow_up_timeframe: string;
  conversation_quality: string;
  call_score: number;
}

interface ActiveCall {
  call_id: string;
  call_sid: string;
  client_name: string;
  client_phone: string;
  agent_name: string;
  status: string;
  started_at: string;
  duration_seconds: number;
  current_stage: string;
  conversation_turns: number;
  last_activity: string;
}

interface SystemHealth {
  status: string;
  timestamp: string;
  components: {
    voice_processor: { configured: boolean; status: string };
    hybrid_tts: {
      configured: boolean;
      status: string;
      stats?: Record<string, unknown>;
    };
    lyzr: {
      configured: boolean;
      status: string;
      conversation_agent?: string;
      summary_agent?: string;
      test_latency_ms?: number;
    };
    elevenlabs: {
      configured: boolean;
      status: string;
      test_latency_ms?: number;
      default_voice?: string;
    };
    deepgram: {
      configured: boolean;
      status: string;
      test_latency_ms?: number;
      model?: string;
    };
    database: { connected: boolean; status: string };
    redis: { connected: boolean; status: string };
    twilio: { configured: boolean; status: string; phone_number?: string };
  };
  metrics?: Record<string, unknown>;
  alerts?: Array<{
    level: string;
    service: string;
    message: string;
  }>;
  campaign?: {
    total_clients: number;
    completed_calls: number;
    completion_rate: number;
  };
}

interface TestStats {
  total_test_calls: number;
  successful_calls: number;
  failed_calls: number;
  avg_duration: string;
  success_rate: number;
  avg_response_time: string;
}

const FormRow = ({ children }: { children: React.ReactNode }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
);

export default function Testing() {
  const [newClient, setNewClient] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    email: "",
    notes: "",
  });
  const [newAgent, setNewAgent] = useState({
    name: "",
    email: "",
    google_calendar_id: "",
    timezone: "America/New_York",
  });

  const [isCreatingClient, setIsCreatingClient] = useState(false);
  const [isCreatingAgent, setIsCreatingAgent] = useState(false);
  const [isCallInProgress, setIsCallInProgress] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [testClients, setTestClients] = useState<TestClient[]>([]);
  const [testAgents, setTestAgents] = useState<TestAgent[]>([]);
  const [callLogs, setCallLogs] = useState<CallLog[]>([]);
  const [activeCalls, setActiveCalls] = useState<ActiveCall[]>([]);
  const [selectedClient, setSelectedClient] = useState("");
  const [selectedAgent, setSelectedAgent] = useState("");
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [testStats, setTestStats] = useState<TestStats | null>(null);
  const [selectedCallSummary, setSelectedCallSummary] =
    useState<CallSummary | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  const loadData = async (
    type?:
      | "clients"
      | "agents"
      | "call-logs"
      | "active-calls"
      | "health"
      | "stats"
  ) => {
    setIsLoadingData(true);
    try {
      if (!type || type === "clients") {
        const clientsRes = await fetch(
          `${API_BASE}/api/dashboard/test-clients`
        );
        const clientsData = await clientsRes.json();
        setTestClients(clientsData.clients || []);
      }

      if (!type || type === "agents") {
        const agentsRes = await fetch(`${API_BASE}/api/dashboard/test-agents`);
        const agentsData = await agentsRes.json();
        setTestAgents(agentsData.agents || []);
      }

      if (!type || type === "call-logs") {
        const logsRes = await fetch(
          `${API_BASE}/api/dashboard/call-logs?limit=50`
        );
        const logsData = await logsRes.json();
        const testCallLogs = (logsData.logs || []).filter(
          (log: Record<string, unknown>) => log.is_test_call
        );
        setCallLogs(testCallLogs);
      }

      if (!type || type === "active-calls") {
        const activeRes = await fetch(`${API_BASE}/api/dashboard/active-calls`);
        if (activeRes.ok) {
          const activeData = await activeRes.json();
          setActiveCalls(activeData.active_calls || []);
        }
      }

      if (!type || type === "health") {
        try {
          const healthRes = await fetch(
            `${API_BASE}/api/dashboard/system-health`
          );
          if (healthRes.ok) {
            const healthData = await healthRes.json();
            setSystemHealth(healthData);
          } else {
            console.error("Failed to fetch system health");
            setSystemHealth(null);
          }
        } catch (error) {
          console.error("Error fetching system health:", error);
          setSystemHealth(null);
        }
      }

      if (!type || type === "stats") {
        const testCalls = callLogs.filter((call) => call.is_test_call);
        const successfulCalls = testCalls.filter((call) =>
          [
            "interested",
            "not_interested",
            "dnc_requested",
            "scheduled_morning",
            "scheduled_afternoon",
          ].includes(call.outcome)
        );

        setTestStats({
          total_test_calls: testCalls.length,
          successful_calls: successfulCalls.length,
          failed_calls: testCalls.length - successfulCalls.length,
          avg_duration: testCalls.length > 0 ? "2m 34s" : "0s",
          success_rate:
            testCalls.length > 0
              ? (successfulCalls.length / testCalls.length) * 100
              : 0,
          avg_response_time: "1.2s",
        });
      }
    } catch (error) {
      console.error(`Failed to load data:`, error);
      toast.error("Failed to load data", {
        description: "Please check the API connection and try again.",
      });
    } finally {
      setIsLoadingData(false);
    }
  };

  useEffect(() => {
    loadData();
    // Reduced polling frequency and made it conditional
    const interval = setInterval(() => {
      // Only poll if there are active calls or if we're on the testing page
      if (activeCalls.length > 0) {
        loadData("call-logs");
        loadData("active-calls");
        loadData("health");
      } else {
        // Less frequent polling when no active calls
        loadData("call-logs");
      }
    }, 60000); // Changed from 10000 to 60000 (1 minute)
    return () => clearInterval(interval);
  }, [activeCalls.length]); // Added dependency to re-create interval when active calls change

  const handleCreateClient = async () => {
    setIsCreatingClient(true);
    try {
      const response = await fetch(`${API_BASE}/api/dashboard/test-clients`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newClient),
      });
      const result = await response.json();
      if (result.success) {
        toast.success(result.message);
        setNewClient({
          first_name: "",
          last_name: "",
          phone: "",
          email: "",
          notes: "",
        });
        loadData("clients");
      } else {
        toast.error("Error creating client", {
          description: result.detail || "Failed to create client.",
        });
      }
    } catch {
      toast.error("An unexpected error occurred.");
    }
    setIsCreatingClient(false);
  };

  const handleCreateAgent = async () => {
    setIsCreatingAgent(true);
    try {
      const response = await fetch(`${API_BASE}/api/dashboard/test-agents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...newAgent, specialties: [] }),
      });
      const result = await response.json();
      if (result.success) {
        toast.success(result.message);
        setNewAgent({
          name: "",
          email: "",
          google_calendar_id: "",
          timezone: "America/New_York",
        });
        loadData("agents");
      } else {
        toast.error("Error creating agent", {
          description: result.detail || "Failed to create agent.",
        });
      }
    } catch {
      toast.error("An unexpected error occurred.");
    }
    setIsCreatingAgent(false);
  };

  const handleStartTestCall = async () => {
    if (!selectedClient || !selectedAgent) return;
    setIsCallInProgress(true);

    try {
      const response = await fetch(`${API_BASE}/api/dashboard/test-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: selectedClient,
          agent_id: selectedAgent,
          call_type: "test",
        }),
      });
      const result = await response.json();

      if (result.success) {
        toast.success("Real test call initiated!", {
          description: `Calling ${result.client_phone} - Call SID: ${result.call_sid}`,
        });

        const newActiveCall: ActiveCall = {
          call_id: result.call_id,
          call_sid: result.call_sid,
          client_name: result.client_name,
          client_phone: result.client_phone,
          agent_name: result.agent_name,
          status: result.status || "initiated",
          started_at: new Date().toISOString(),
          duration_seconds: 0,
          current_stage: "call_initiated",
          conversation_turns: 0,
          last_activity: new Date().toISOString(),
        };
        setActiveCalls((prev) => [...prev, newActiveCall]);
        pollCallStatus(result.call_sid);
      } else {
        toast.error("Test call failed", {
          description: result.detail || "Failed to start test call.",
        });
      }
    } catch {
      toast.error("An unexpected error occurred.");
    }
    setIsCallInProgress(false);
  };

  const pollCallStatus = async (callSid: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const statusRes = await fetch(
          `${API_BASE}/api/dashboard/call-status/${callSid}`
        );
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          setActiveCalls((prev) =>
            prev.map((call) =>
              call.call_sid === callSid
                ? {
                    ...call,
                    status: statusData.status,
                    current_stage: statusData.stage,
                  }
                : call
            )
          );
          // Stop polling when call is completed or failed
          if (
            ["completed", "failed", "busy", "no_answer"].includes(
              statusData.status
            )
          ) {
            clearInterval(pollInterval);
            loadData("call-logs");
            loadData("clients");
            setActiveCalls((prev) =>
              prev.filter((call) => call.call_sid !== callSid)
            );
          }
        }
      } catch (error) {
        console.error("Failed to poll call status:", error);
      }
    }, 5000); // Changed from 3000 to 5000 (5 seconds)
    // Stop polling after 5 minutes instead of 5 minutes
    setTimeout(() => clearInterval(pollInterval), 300000);
  };

  const handleDeleteClient = async (clientId: string) => {
    try {
      const response = await fetch(
        `${API_BASE}/api/dashboard/test-clients/${clientId}`,
        {
          method: "DELETE",
        }
      );
      if (response.ok) {
        toast.success("Test client deleted");
        loadData("clients");
      } else {
        toast.error("Failed to delete client");
      }
    } catch {
      toast.error("Error deleting client");
    }
  };

  const viewCallSummary = async (callLog: CallLog) => {
    try {
      const summaryRes = await fetch(
        `${API_BASE}/api/dashboard/call-details/${callLog.call_id}`
      );
      if (summaryRes.ok) {
        const summaryData = await summaryRes.json();
        setSelectedCallSummary(summaryData.summary);
      } else {
        toast.error("Failed to load call summary");
      }
    } catch {
      toast.error("Error loading call summary");
    }
  };

  const getStatusBadge = (status: string) => {
    const statusMap = {
      initiated: { variant: "secondary" as const, color: "text-blue-600" },
      ringing: { variant: "secondary" as const, color: "text-yellow-600" },
      answered: { variant: "default" as const, color: "text-green-600" },
      in_progress: { variant: "default" as const, color: "text-green-600" },
      completed: { variant: "outline" as const, color: "text-gray-600" },
      failed: { variant: "destructive" as const, color: "text-red-600" },
      busy: { variant: "secondary" as const, color: "text-orange-600" },
      no_answer: { variant: "outline" as const, color: "text-gray-600" },
      unknown: { variant: "outline" as const, color: "text-gray-600" },
    };
    return statusMap[status as keyof typeof statusMap] || statusMap.unknown;
  };

  const getOutcomeBadge = (outcome: string) => {
    const outcomeMap = {
      interested: { variant: "default" as const, color: "text-green-600" },
      not_interested: { variant: "secondary" as const, color: "text-gray-600" },
      dnc_requested: { variant: "destructive" as const, color: "text-red-600" },
      scheduled_morning: {
        variant: "default" as const,
        color: "text-green-600",
      },
      scheduled_afternoon: {
        variant: "default" as const,
        color: "text-green-600",
      },
      no_answer: { variant: "outline" as const, color: "text-yellow-600" },
      completed: { variant: "outline" as const, color: "text-gray-600" },
    };
    return (
      outcomeMap[outcome as keyof typeof outcomeMap] || outcomeMap.completed
    );
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Voice Agent Testing & Monitoring
          </h1>
          <p className="text-muted-foreground mt-1">
            Complete testing environment with real call capabilities, live
            monitoring, and production-like data visualization.
          </p>
        </div>
        <Button
          onClick={() => loadData()}
          disabled={isLoadingData}
          size="sm"
          variant="outline"
        >
          <RefreshCw
            className={`h-4 w-4 ${isLoadingData ? "animate-spin" : ""}`}
          />
          <span className="ml-2">Refresh Data</span>
        </Button>
      </div>

      {systemHealth &&
        systemHealth.status !== "healthy" &&
        systemHealth.status !== "all_systems_operational" && (
          <Card className="border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-900/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
                <AlertTriangle className="h-5 w-5" />
                System Health Warning
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-yellow-700 dark:text-yellow-300">
                Some system components are not fully operational. Check the
                System Health tab for details.
              </p>
              {systemHealth.alerts && systemHealth.alerts.length > 0 && (
                <div className="mt-2 space-y-1">
                  {systemHealth.alerts.map((alert, idx) => (
                    <div key={idx} className="text-sm">
                      <span className="font-medium capitalize">
                        {alert.level}:
                      </span>{" "}
                      {alert.message}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

      {activeCalls.length > 0 && (
        <Card className="border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-800 dark:text-green-200">
              <PhoneCall className="h-5 w-5 animate-pulse" />
              Active Test Calls ({activeCalls.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {activeCalls.map((call) => (
                <div
                  key={call.call_id}
                  className="flex items-center justify-between p-3 bg-background rounded-lg border"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-green-600" />
                      <span className="font-medium">{call.client_name}</span>
                    </div>
                    <Badge {...getStatusBadge(call.status || "unknown")}>
                      {(call.status || "unknown").replace("_", " ")}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      Stage:{" "}
                      {(call.current_stage || "unknown").replace("_", " ")}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      Turns: {call.conversation_turns}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    {new Date(call.started_at).toLocaleTimeString()}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-6"
      >
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="create">Create Data</TabsTrigger>
          <TabsTrigger value="test-calls">Test Calls</TabsTrigger>
          <TabsTrigger value="call-logs">Call Logs</TabsTrigger>
          <TabsTrigger value="health">System Health</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Total Test Calls
                </CardTitle>
                <PhoneCall className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {testStats?.total_test_calls || 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  All test executions
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Success Rate
                </CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {testStats?.success_rate.toFixed(1) || 0}%
                </div>
                <Progress
                  value={testStats?.success_rate || 0}
                  className="mt-2"
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Avg Response Time
                </CardTitle>
                <Timer className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {testStats?.avg_response_time || "0s"}
                </div>
                <p className="text-xs text-muted-foreground">Target: &lt;2s</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Test Entities
                </CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {testClients.length + testAgents.length}
                </div>
                <p className="text-xs text-muted-foreground">
                  {testClients.length} clients, {testAgents.length} agents
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Quick Test Actions</CardTitle>
              <CardDescription>
                Rapid testing and system validation
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Button
                  onClick={() => setActiveTab("test-calls")}
                  className="flex items-center gap-2"
                >
                  <Play className="h-4 w-4" />
                  Start Test Call
                </Button>
                <Button
                  variant="outline"
                  onClick={() => loadData()}
                  disabled={isLoadingData}
                >
                  <RefreshCw
                    className={`h-4 w-4 mr-2 ${
                      isLoadingData ? "animate-spin" : ""
                    }`}
                  />
                  Refresh All Data
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setActiveTab("health");
                    loadData("health");
                  }}
                >
                  <Activity className="h-4 w-4 mr-2" />
                  Check System Health
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Test Activity</CardTitle>
              <CardDescription>
                Latest test calls and system events
              </CardDescription>
            </CardHeader>
            <CardContent>
              {callLogs.filter((log) => log.is_test_call).slice(0, 5).length >
              0 ? (
                <div className="space-y-3">
                  {callLogs
                    .filter((log) => log.is_test_call)
                    .slice(0, 5)
                    .map((log) => (
                      <div
                        key={log.call_id}
                        className="flex items-center justify-between p-3 border rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <Badge {...getOutcomeBadge(log.outcome)}>
                            {log.outcome.replace("_", " ")}
                          </Badge>
                          <span className="font-medium">{log.client_name}</span>
                          <span className="text-sm text-muted-foreground">
                            {log.duration}
                          </span>
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {new Date(log.started_at).toLocaleString()}
                        </span>
                      </div>
                    ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No recent test activity found
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="create" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <User className="h-5 w-5" /> Create Test Client
                </CardTitle>
                <CardDescription>
                  Add a new client to the database for testing.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <FormRow>
                  <div className="space-y-1.5">
                    <Label htmlFor="firstName">First Name</Label>
                    <Input
                      id="firstName"
                      value={newClient.first_name}
                      onChange={(e) =>
                        setNewClient({
                          ...newClient,
                          first_name: e.target.value,
                        })
                      }
                      placeholder="John"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lastName">Last Name</Label>
                    <Input
                      id="lastName"
                      value={newClient.last_name}
                      onChange={(e) =>
                        setNewClient({
                          ...newClient,
                          last_name: e.target.value,
                        })
                      }
                      placeholder="Doe"
                    />
                  </div>
                </FormRow>
                <FormRow>
                  <div className="space-y-1.5">
                    <Label htmlFor="phone">Phone Number</Label>
                    <Input
                      id="phone"
                      type="tel"
                      value={newClient.phone}
                      onChange={(e) =>
                        setNewClient({ ...newClient, phone: e.target.value })
                      }
                      placeholder="+1234567890"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="email">Email (optional)</Label>
                    <Input
                      id="email"
                      type="email"
                      value={newClient.email || ""}
                      onChange={(e) =>
                        setNewClient({ ...newClient, email: e.target.value })
                      }
                      placeholder="john@example.com"
                    />
                  </div>
                </FormRow>
                <div className="space-y-1.5">
                  <Label htmlFor="notes">Notes (optional)</Label>
                  <Textarea
                    id="notes"
                    value={newClient.notes || ""}
                    onChange={(e) =>
                      setNewClient({ ...newClient, notes: e.target.value })
                    }
                    placeholder="Additional test notes..."
                    rows={3}
                  />
                </div>
                <Button
                  onClick={handleCreateClient}
                  disabled={
                    isCreatingClient ||
                    !newClient.first_name ||
                    !newClient.phone
                  }
                  className="w-full"
                >
                  {isCreatingClient ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <PlusCircle className="mr-2 h-4 w-4" />
                  )}
                  Create Test Client
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Rocket className="h-5 w-5" /> Create Test Agent
                </CardTitle>
                <CardDescription>
                  Add a new agent to the database for testing.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <FormRow>
                  <div className="space-y-1.5">
                    <Label htmlFor="agentName">Agent Name</Label>
                    <Input
                      id="agentName"
                      value={newAgent.name}
                      onChange={(e) =>
                        setNewAgent({ ...newAgent, name: e.target.value })
                      }
                      placeholder="Jane Smith"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="agentEmail">Email</Label>
                    <Input
                      id="agentEmail"
                      type="email"
                      value={newAgent.email}
                      onChange={(e) =>
                        setNewAgent({ ...newAgent, email: e.target.value })
                      }
                      placeholder="jane@example.com"
                    />
                  </div>
                </FormRow>
                <FormRow>
                  <div className="space-y-1.5">
                    <Label htmlFor="googleCalendar">Google Calendar ID</Label>
                    <Input
                      id="googleCalendar"
                      value={newAgent.google_calendar_id}
                      onChange={(e) =>
                        setNewAgent({
                          ...newAgent,
                          google_calendar_id: e.target.value,
                        })
                      }
                      placeholder="jane@company.com"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="timezone">Timezone</Label>
                    <Select
                      value={newAgent.timezone}
                      onValueChange={(value) =>
                        setNewAgent({ ...newAgent, timezone: value })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="America/New_York">
                          Eastern Time
                        </SelectItem>
                        <SelectItem value="America/Chicago">
                          Central Time
                        </SelectItem>
                        <SelectItem value="America/Denver">
                          Mountain Time
                        </SelectItem>
                        <SelectItem value="America/Los_Angeles">
                          Pacific Time
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </FormRow>
                <Button
                  onClick={handleCreateAgent}
                  disabled={
                    isCreatingAgent || !newAgent.name || !newAgent.email
                  }
                  className="w-full"
                >
                  {isCreatingAgent ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <PlusCircle className="mr-2 h-4 w-4" />
                  )}
                  Create Test Agent
                </Button>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Test Clients ({testClients.length})</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => loadData("clients")}
                    disabled={isLoadingData}
                  >
                    <RefreshCw
                      className={`h-4 w-4 ${
                        isLoadingData ? "animate-spin" : ""
                      }`}
                    />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="max-h-96 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Phone</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {testClients.map((client) => (
                        <TableRow key={client.id}>
                          <TableCell className="font-medium">
                            {client.name}
                          </TableCell>
                          <TableCell className="text-sm">
                            {client.phone}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{client.status}</Badge>
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDeleteClient(client.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Test Agents ({testAgents.length})</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => loadData("agents")}
                    disabled={isLoadingData}
                  >
                    <RefreshCw
                      className={`h-4 w-4 ${
                        isLoadingData ? "animate-spin" : ""
                      }`}
                    />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="max-h-96 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Timezone</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {testAgents.map((agent) => (
                        <TableRow key={agent.id}>
                          <TableCell className="font-medium">
                            {agent.name}
                          </TableCell>
                          <TableCell className="text-sm">
                            {agent.email}
                          </TableCell>
                          <TableCell className="text-sm">
                            {agent.timezone}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="test-calls" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Real Test Call Execution
              </CardTitle>
              <CardDescription>
                Execute real voice calls using Twilio with full production
                pipeline
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <FormRow>
                <div className="space-y-1.5">
                  <Label>Test Client</Label>
                  <div className="flex gap-2">
                    <Select
                      value={selectedClient}
                      onValueChange={setSelectedClient}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select test client" />
                      </SelectTrigger>
                      <SelectContent>
                        {testClients.map((c) => (
                          <SelectItem key={c.id} value={c.id}>
                            {c.name} ({c.phone})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => loadData("clients")}
                    >
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label>Test Agent</Label>
                  <div className="flex gap-2">
                    <Select
                      value={selectedAgent}
                      onValueChange={setSelectedAgent}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select test agent" />
                      </SelectTrigger>
                      <SelectContent>
                        {testAgents.map((a) => (
                          <SelectItem key={a.id} value={a.id}>
                            {a.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => loadData("agents")}
                    >
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </FormRow>

              <div className="border rounded-lg p-4 bg-blue-50 dark:bg-blue-900/20">
                <div className="flex items-start gap-3">
                  <PhoneCall className="h-5 w-5 text-blue-600 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-blue-900 dark:text-blue-200">
                      Real Call Execution
                    </h4>
                    <p className="text-sm text-blue-700 dark:text-blue-300">
                      This will make an actual phone call to the selected client
                      using Twilio. The call will go through the complete
                      production pipeline including Deepgram STT, LYZR
                      conversation processing, and ElevenLabs TTS.
                    </p>
                  </div>
                </div>
              </div>

              <Button
                onClick={handleStartTestCall}
                disabled={isCallInProgress || !selectedClient || !selectedAgent}
                className="w-full"
                size="lg"
              >
                {isCallInProgress ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                {isCallInProgress
                  ? "Initiating Real Call..."
                  : "Start Real Test Call"}
              </Button>

              {isCallInProgress && (
                <Card className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20">
                  <CardContent className="pt-6">
                    <div className="space-y-4">
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                        <span className="text-blue-800 font-medium dark:text-blue-200">
                          Call in progress...
                        </span>
                      </div>
                      <Progress value={33} className="w-full" />
                      <p className="text-sm text-blue-600 dark:text-blue-300">
                        The system is processing your test call. You should
                        receive a call shortly.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5" />
                Performance Testing
              </CardTitle>
              <CardDescription>
                Latency and quality metrics for voice processing pipeline
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 border rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Mic className="h-4 w-4 text-blue-500" />
                    <span className="font-medium">Speech-to-Text</span>
                  </div>
                  <div className="text-2xl font-bold">432ms</div>
                  <div className="text-sm text-muted-foreground">
                    Target: &lt;500ms
                  </div>
                  <Progress value={86} className="mt-2" />
                </div>

                <div className="p-4 border rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="h-4 w-4 text-green-500" />
                    <span className="font-medium">AI Processing</span>
                  </div>
                  <div className="text-2xl font-bold">1.2s</div>
                  <div className="text-sm text-muted-foreground">
                    Target: &lt;1.5s
                  </div>
                  <Progress value={80} className="mt-2" />
                </div>

                <div className="p-4 border rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Speaker className="h-4 w-4 text-purple-500" />
                    <span className="font-medium">Text-to-Speech</span>
                  </div>
                  <div className="text-2xl font-bold">720ms</div>
                  <div className="text-sm text-muted-foreground">
                    Target: &lt;900ms
                  </div>
                  <Progress value={80} className="mt-2" />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="call-logs" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>
                    Test Call Logs & History ({callLogs.length})
                  </CardTitle>
                  <CardDescription>
                    Complete test call records with summaries and performance
                    metrics
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => loadData("call-logs")}
                  disabled={isLoadingData}
                >
                  <RefreshCw
                    className={`h-4 w-4 ${isLoadingData ? "animate-spin" : ""}`}
                  />
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Call Details</TableHead>
                      <TableHead>Client</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Outcome</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Started</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {callLogs
                      .filter((log) => log.is_test_call)
                      .map((log) => (
                        <TableRow key={log.call_id}>
                          <TableCell>
                            <div>
                              <div className="font-mono text-xs text-muted-foreground">
                                {log.call_sid?.substring(0, 8)}...
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Turns: {log.conversation_turns || 0}
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div>
                              <div className="font-medium">
                                {log.client_name}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {log.client_phone}
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge {...getStatusBadge(log.status)}>
                              {log.status.replace("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge {...getOutcomeBadge(log.outcome)}>
                              {log.outcome.replace("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell>{log.duration}</TableCell>
                          <TableCell>
                            <div className="text-sm">
                              {new Date(log.started_at).toLocaleDateString()}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {new Date(log.started_at).toLocaleTimeString()}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Dialog>
                              <DialogTrigger asChild>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => viewCallSummary(log)}
                                >
                                  <Eye className="h-4 w-4" />
                                </Button>
                              </DialogTrigger>
                              <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
                                <DialogHeader>
                                  <DialogTitle>
                                    Call Summary & Analysis
                                  </DialogTitle>
                                  <DialogDescription>
                                    Complete AI-generated analysis for call with{" "}
                                    {log.client_name}
                                  </DialogDescription>
                                </DialogHeader>
                                {selectedCallSummary && (
                                  <div className="space-y-6">
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                      <div className="p-3 border rounded-lg">
                                        <Label className="text-xs">
                                          Outcome
                                        </Label>
                                        <div className="mt-1">
                                          <Badge
                                            {...getOutcomeBadge(
                                              selectedCallSummary.outcome
                                            )}
                                          >
                                            {selectedCallSummary.outcome.replace(
                                              "_",
                                              " "
                                            )}
                                          </Badge>
                                        </div>
                                      </div>
                                      <div className="p-3 border rounded-lg">
                                        <Label className="text-xs">
                                          Sentiment
                                        </Label>
                                        <div className="mt-1">
                                          <Badge variant="outline">
                                            {selectedCallSummary.sentiment}
                                          </Badge>
                                        </div>
                                      </div>
                                      <div className="p-3 border rounded-lg">
                                        <Label className="text-xs">
                                          Urgency
                                        </Label>
                                        <div className="mt-1">
                                          <Badge variant="secondary">
                                            {selectedCallSummary.urgency}
                                          </Badge>
                                        </div>
                                      </div>
                                      <div className="p-3 border rounded-lg">
                                        <Label className="text-xs">
                                          Quality Score
                                        </Label>
                                        <div className="text-2xl font-bold mt-1">
                                          {selectedCallSummary.call_score}/10
                                        </div>
                                      </div>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                      <div className="space-y-3">
                                        <div>
                                          <Label className="font-medium">
                                            Key Points
                                          </Label>
                                          <ul className="list-disc list-inside text-sm space-y-1 mt-2">
                                            {selectedCallSummary.key_points?.map(
                                              (point, i) => (
                                                <li key={i}>{point}</li>
                                              )
                                            )}
                                          </ul>
                                        </div>
                                        <div>
                                          <Label className="font-medium">
                                            Customer Concerns
                                          </Label>
                                          <ul className="list-disc list-inside text-sm space-y-1 mt-2">
                                            {selectedCallSummary.customer_concerns?.map(
                                              (concern, i) => (
                                                <li key={i}>{concern}</li>
                                              )
                                            )}
                                          </ul>
                                        </div>
                                      </div>
                                      <div className="space-y-3">
                                        <div>
                                          <Label className="font-medium">
                                            Recommended Actions
                                          </Label>
                                          <ul className="list-disc list-inside text-sm space-y-1 mt-2">
                                            {selectedCallSummary.recommended_actions?.map(
                                              (action, i) => (
                                                <li key={i}>{action}</li>
                                              )
                                            )}
                                          </ul>
                                        </div>
                                        <div>
                                          <Label className="font-medium">
                                            Follow-up Timeframe
                                          </Label>
                                          <p className="text-sm mt-2">
                                            {
                                              selectedCallSummary.follow_up_timeframe
                                            }
                                          </p>
                                        </div>
                                      </div>
                                    </div>
                                    <div>
                                      <Label className="font-medium">
                                        AI Agent Notes
                                      </Label>
                                      <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                        <p className="text-sm">
                                          {selectedCallSummary.agent_notes}
                                        </p>
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </DialogContent>
                            </Dialog>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="health" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-5 w-5" />
                    System Health & Status
                  </CardTitle>
                  <CardDescription>
                    Real-time monitoring of all voice agent components
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => loadData("health")}
                  disabled={isLoadingData}
                >
                  <RefreshCw
                    className={`h-4 w-4 ${isLoadingData ? "animate-spin" : ""}`}
                  />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {systemHealth ? (
                <div className="space-y-6">
                  <div className="flex items-center gap-4">
                    <Badge
                      variant={
                        systemHealth.status === "healthy"
                          ? "default"
                          : "destructive"
                      }
                      className="text-lg px-4 py-1"
                    >
                      {systemHealth.status.toUpperCase()}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      Last updated:{" "}
                      {new Date(systemHealth.timestamp).toLocaleString()}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {Object.entries(systemHealth.components).map(
                      ([key, component]) => (
                        <Card key={key}>
                          <CardHeader className="pb-3">
                            <CardTitle className="text-sm font-medium capitalize">
                              {key.replace(/_/g, " ")}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="flex items-center justify-between">
                              <Badge
                                variant={
                                  component.status === "ready"
                                    ? "default"
                                    : "destructive"
                                }
                              >
                                {component.status}
                              </Badge>
                              {"test_latency_ms" in component &&
                                component.test_latency_ms && (
                                  <span className="text-xs text-muted-foreground">
                                    {component.test_latency_ms.toFixed(0)}ms
                                  </span>
                                )}
                            </div>
                          </CardContent>
                        </Card>
                      )
                    )}
                  </div>

                  {systemHealth.alerts && systemHealth.alerts.length > 0 && (
                    <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20">
                      <CardHeader>
                        <CardTitle className="text-red-800 dark:text-red-200">
                          Active Alerts
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {systemHealth.alerts.map((alert, idx) => (
                            <div key={idx} className="flex items-start gap-2">
                              <AlertTriangle className="h-4 w-4 text-red-600 mt-0.5" />
                              <div>
                                <span className="font-medium capitalize">
                                  {alert.level}:
                                </span>{" "}
                                {alert.message}
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {systemHealth.campaign && (
                    <Card>
                      <CardHeader>
                        <CardTitle>Campaign Statistics</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="p-4 border rounded-lg">
                            <div className="text-2xl font-bold">
                              {systemHealth.campaign.total_clients}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              Total Clients
                            </div>
                          </div>
                          <div className="p-4 border rounded-lg">
                            <div className="text-2xl font-bold">
                              {systemHealth.campaign.completed_calls}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              Completed Calls
                            </div>
                          </div>
                          <div className="p-4 border rounded-lg">
                            <div className="text-2xl font-bold">
                              {systemHealth.campaign.completion_rate.toFixed(1)}
                              %
                            </div>
                            <div className="text-sm text-muted-foreground">
                              Completion Rate
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                  Loading system health data...
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
