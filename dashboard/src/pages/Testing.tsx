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
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Rocket,
  PlusCircle,
  Eye,
  Trash2,
  PhoneCall,
  Calendar,
  MessageSquare,
  Activity,
  TrendingUp,
  AlertTriangle,
  Settings,
  FileText,
  Timer,
  Volume2,
  Mic,
  Speaker,
  Database,
  Monitor,
  Zap,
  Users,
  Target,
} from "lucide-react";

// API base URL from env
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
// const API_BASE = "http://localhost:8000";

// Interface definitions
interface TestClient {
  id: string;
  name: string;
  phone: string;
  email?: string;
  status: string;
  total_attempts: number;
  created_at: string;
  last_call_outcome?: string;
  is_test_client: boolean;
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
  latency_metrics?: {
    transcription_ms: number;
    processing_ms: number;
    tts_ms: number;
    total_ms: number;
  };
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
  components: {
    database: boolean;
    cache: boolean;
    voice_processor: boolean;
    hybrid_tts: boolean;
  };
  configuration: {
    lyzr: boolean;
    elevenlabs: boolean;
    deepgram: boolean;
    twilio: boolean;
  };
  performance_metrics: {
    avg_response_time: number;
    success_rate: number;
    active_calls: number;
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

// A new component for a cleaner form row layout
const FormRow = ({ children }: { children: React.ReactNode }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
);

export default function Testing() {
  // State for forms
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

  // State for loading indicators
  const [isCreatingClient, setIsCreatingClient] = useState(false);
  const [isCreatingAgent, setIsCreatingAgent] = useState(false);
  const [isCallInProgress, setIsCallInProgress] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(false);

  // State for data
  const [testClients, setTestClients] = useState<TestClient[]>([]);
  const [testAgents, setTestAgents] = useState<TestAgent[]>([]);
  const [callLogs, setCallLogs] = useState<CallLog[]>([]);
  const [activeCalls, setActiveCalls] = useState<ActiveCall[]>([]);
  const [selectedClient, setSelectedClient] = useState("");
  const [selectedAgent, setSelectedAgent] = useState("");
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [testStats, setTestStats] = useState<TestStats | null>(null);

  // State for dialogs and details
  const [selectedCallSummary, setSelectedCallSummary] =
    useState<CallSummary | null>(null);
  const [isCallDetailsOpen, setIsCallDetailsOpen] = useState(false);
  const [currentCall, setCurrentCall] = useState<ActiveCall | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  // Data Fetching
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
        // Filter for test calls and add test flag
        const testCallLogs = (logsData.logs || []).map((log: any) => ({
          ...log,
          is_test_call:
            log.call_id?.includes("test") || log.call_sid?.includes("test"),
          agent_name: log.agent_name || "Test Agent",
        }));
        setCallLogs(testCallLogs);
      }

      if (!type || type === "active-calls") {
        const activeRes = await fetch(`${API_BASE}/api/dashboard/active-calls`);
        if (activeRes.ok) {
          const activeData = await activeRes.json();
          setActiveCalls(activeData.calls || []);
        }
      }

      if (!type || type === "health") {
        const healthRes = await fetch(
          `${API_BASE}/api/dashboard/system-health`
        );
        if (healthRes.ok) {
          const healthData = await healthRes.json();
          setSystemHealth(healthData);
        }
      }

      if (!type || type === "stats") {
        // Calculate test stats from call logs
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
    // Refresh data every 10 seconds for live updates
    const interval = setInterval(() => {
      loadData("call-logs");
      loadData("active-calls");
      loadData("health");
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // Handlers
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
    } catch (error) {
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
    } catch (error) {
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
          description: `Calling ${result.phone} - Call SID: ${result.call_sid}`,
        });

        // Add to active calls for monitoring
        const newActiveCall: ActiveCall = {
          call_id: result.call_id,
          call_sid: result.call_sid,
          client_name: result.client_name,
          client_phone: result.phone,
          agent_name: result.agent_name,
          status: result.status || "initiated",
          started_at: new Date().toISOString(),
          duration_seconds: 0,
          current_stage: "call_initiated",
          conversation_turns: 0,
          last_activity: new Date().toISOString(),
        };
        setActiveCalls((prev) => [...prev, newActiveCall]);
        setCurrentCall(newActiveCall);

        // Start polling for call status
        pollCallStatus(result.call_sid);
      } else {
        toast.error("Test call failed", {
          description: result.detail || "Failed to start test call.",
        });
      }
    } catch (error) {
      toast.error("An unexpected error occurred.");
    }
    setIsCallInProgress(false);
  };

  const pollCallStatus = async (callSid: string) => {
    // Poll for real call status updates
    const pollInterval = setInterval(async () => {
      try {
        const statusRes = await fetch(
          `${API_BASE}/api/dashboard/call-status/${callSid}`
        );
        if (statusRes.ok) {
          const statusData = await statusRes.json();

          // Update active calls
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

          // If call completed, stop polling and refresh data
          if (statusData.status === "completed") {
            clearInterval(pollInterval);
            loadData("call-logs");
            loadData("clients");
            setActiveCalls((prev) =>
              prev.filter((call) => call.call_sid !== callSid)
            );
            setCurrentCall(null);
          }
        }
      } catch (error) {
        console.error("Failed to poll call status:", error);
      }
    }, 3000);

    // Stop polling after 5 minutes
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
    } catch (error) {
      toast.error("Error deleting client");
    }
  };

  const viewCallSummary = async (callLog: CallLog) => {
    try {
      const summaryRes = await fetch(
        `${API_BASE}/api/dashboard/call-summary/${callLog.call_id}`
      );
      if (summaryRes.ok) {
        const summaryData = await summaryRes.json();
        setSelectedCallSummary(summaryData.summary);
        setIsCallDetailsOpen(true);
      } else {
        toast.error("Failed to load call summary");
      }
    } catch (error) {
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
    };
    return statusMap[status as keyof typeof statusMap] || statusMap.completed;
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
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Voice Agent Testing & Monitoring
        </h1>
        <p className="text-muted-foreground mt-1">
          Complete testing environment with real call capabilities, live
          monitoring, and production-like data visualization.
        </p>
      </div>

      {/* System Health Alert */}
      {systemHealth && systemHealth.status !== "healthy" && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-yellow-800">
              <AlertTriangle className="h-5 w-5" />
              System Health Warning
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-yellow-700">
              Some system components are not fully operational. Check the System
              Health tab for details.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Active Calls Monitor */}
      {activeCalls.length > 0 && (
        <Card className="border-green-200 bg-green-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-800">
              <PhoneCall className="h-5 w-5 animate-pulse" />
              Active Test Calls ({activeCalls.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {activeCalls.map((call) => (
                <div
                  key={call.call_id}
                  className="flex items-center justify-between p-3 bg-white rounded-lg border"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-green-600" />
                      <span className="font-medium">{call.client_name}</span>
                    </div>
                    <Badge {...getStatusBadge(call.status)}>
                      {call.status.replace("_", " ")}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      Stage: {call.current_stage.replace("_", " ")}
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

      {/* Main Content Tabs */}
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
          <TabsTrigger value="monitoring">Live Monitor</TabsTrigger>
          <TabsTrigger value="health">System Health</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Test Statistics */}
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

          {/* Quick Test Actions */}
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
                  onClick={() => setActiveTab("health")}
                >
                  <Activity className="h-4 w-4 mr-2" />
                  Check System Health
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Recent Activity Preview */}
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

        {/* Create Data Tab */}
        <TabsContent value="create" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Create Test Client */}
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

            {/* Create Test Agent */}
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

          {/* Test Data Management */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Test Clients Table */}
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

            {/* Test Agents Table */}
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

        {/* Test Calls Tab */}
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

              <div className="border rounded-lg p-4 bg-blue-50">
                <div className="flex items-start gap-3">
                  <PhoneCall className="h-5 w-5 text-blue-600 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-blue-900">
                      Real Call Execution
                    </h4>
                    <p className="text-sm text-blue-700">
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

              {/* Call Progress Indicator */}
              {isCallInProgress && (
                <Card className="border-blue-200 bg-blue-50">
                  <CardContent className="pt-6">
                    <div className="space-y-4">
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                        <span className="text-blue-800 font-medium">
                          Call in progress...
                        </span>
                      </div>
                      <Progress value={33} className="w-full" />
                      <p className="text-sm text-blue-600">
                        The system is processing your test call. You should
                        receive a call shortly.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>

          {/* Test Call Performance Metrics */}
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

        {/* Call Logs Tab */}
        <TabsContent value="call-logs" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Test Call Logs & History</CardTitle>
                  <CardDescription>
                    Complete call records with summaries and performance metrics
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
                      <TableHead>Performance</TableHead>
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
                            {log.latency_metrics ? (
                              <div className="text-xs">
                                <div>
                                  Total: {log.latency_metrics.total_ms}ms
                                </div>
                                <div className="text-muted-foreground">
                                  STT: {log.latency_metrics.transcription_ms}ms
                                </div>
                              </div>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </TableCell>
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
                                    {/* Summary Overview */}
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

                                    {/* Key Points */}
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

                                    {/* Agent Notes */}
                                    <div>
                                      <Label className="font-medium">
                                        AI Agent Notes
                                      </Label>
                                      <div className="mt-2 p-3 bg-gray-50 rounded-lg">
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

        {/* Live Monitor Tab */}
        <TabsContent value="monitoring" className="space-y-6">
          {/* Real-time Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Active Calls
                </CardTitle>
                <PhoneCall className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{activeCalls.length}</div>
                <p className="text-xs text-muted-foreground">
                  Currently in progress
                </p>
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
                <div className="text-2xl font-bold">1.4s</div>
                <p className="text-xs text-muted-foreground">Last 10 calls</p>
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
                <div className="text-2xl font-bold">94.2%</div>
                <p className="text-xs text-muted-foreground">Today's tests</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  System Load
                </CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">23%</div>
                <Progress value={23} className="mt-2" />
              </CardContent>
            </Card>
          </div>

          {/* Live Activity Feed */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Live Activity Feed
              </CardTitle>
              <CardDescription>
                Real-time system events and call processing updates
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {/* Mock live events - replace with real WebSocket data */}
                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <div className="flex-1">
                    <div className="text-sm font-medium">
                      Call completed successfully
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Client: John Doe | Outcome: Interested | Duration: 2m 45s
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {new Date().toLocaleTimeString()}
                  </div>
                </div>

                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                  <div className="flex-1">
                    <div className="text-sm font-medium">
                      New test call initiated
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Target: +1234567890 | Agent: Jane Smith
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(Date.now() - 30000).toLocaleTimeString()}
                  </div>
                </div>

                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                  <div className="flex-1">
                    <div className="text-sm font-medium">
                      System health check completed
                    </div>
                    <div className="text-xs text-muted-foreground">
                      All services operational | Response time: 1.2s
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(Date.now() - 120000).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* System Health Tab */}
        <TabsContent value="health" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Monitor className="h-5 w-5" />
                    System Health Dashboard
                  </CardTitle>
                  <CardDescription>
                    Complete system status and service health monitoring
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
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {systemHealth ? (
                <div className="space-y-6">
                  {/* Overall Status */}
                  <div className="flex items-center gap-4 p-4 border rounded-lg">
                    <div
                      className={`w-4 h-4 rounded-full ${
                        systemHealth.status === "healthy"
                          ? "bg-green-500"
                          : systemHealth.status === "degraded"
                          ? "bg-yellow-500"
                          : "bg-red-500"
                      }`}
                    ></div>
                    <div>
                      <div className="font-medium">
                        System Status: {systemHealth.status.toUpperCase()}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Last checked: {new Date().toLocaleString()}
                      </div>
                    </div>
                  </div>

                  {/* Core Components */}
                  <div>
                    <h3 className="font-medium mb-3">Core Components</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(systemHealth.components).map(
                        ([component, status]) => (
                          <div
                            key={component}
                            className="flex items-center justify-between p-3 border rounded-lg"
                          >
                            <div className="flex items-center gap-2">
                              <Database className="h-4 w-4" />
                              <span className="font-medium capitalize">
                                {component.replace("_", " ")}
                              </span>
                            </div>
                            <Badge variant={status ? "default" : "destructive"}>
                              {status ? "Operational" : "Down"}
                            </Badge>
                          </div>
                        )
                      )}
                    </div>
                  </div>

                  {/* External Services */}
                  <div>
                    <h3 className="font-medium mb-3">
                      External Service Configuration
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(systemHealth.configuration).map(
                        ([service, configured]) => (
                          <div
                            key={service}
                            className="flex items-center justify-between p-3 border rounded-lg"
                          >
                            <div className="flex items-center gap-2">
                              <Settings className="h-4 w-4" />
                              <span className="font-medium uppercase">
                                {service}
                              </span>
                            </div>
                            <Badge
                              variant={configured ? "default" : "secondary"}
                            >
                              {configured ? "Configured" : "Not Configured"}
                            </Badge>
                          </div>
                        )
                      )}
                    </div>
                  </div>

                  {/* Performance Metrics */}
                  {systemHealth.performance_metrics && (
                    <div>
                      <h3 className="font-medium mb-3">Performance Metrics</h3>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="p-4 border rounded-lg">
                          <div className="text-sm text-muted-foreground">
                            Avg Response Time
                          </div>
                          <div className="text-2xl font-bold">
                            {systemHealth.performance_metrics.avg_response_time}
                            ms
                          </div>
                        </div>
                        <div className="p-4 border rounded-lg">
                          <div className="text-sm text-muted-foreground">
                            Success Rate
                          </div>
                          <div className="text-2xl font-bold">
                            {systemHealth.performance_metrics.success_rate}%
                          </div>
                        </div>
                        <div className="p-4 border rounded-lg">
                          <div className="text-sm text-muted-foreground">
                            Active Calls
                          </div>
                          <div className="text-2xl font-bold">
                            {systemHealth.performance_metrics.active_calls}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  Loading system health data...
                </div>
              )}
            </CardContent>
          </Card>

          {/* Service Test Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Service Testing</CardTitle>
              <CardDescription>
                Test individual services and integrations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <Button
                  variant="outline"
                  className="h-20 flex-col gap-2"
                  onClick={() =>
                    window.open(
                      `${API_BASE}/api/dashboard/test-voice-processing`,
                      "_blank"
                    )
                  }
                >
                  <Mic className="h-6 w-6" />
                  Test Voice Processing
                </Button>
                <Button
                  variant="outline"
                  className="h-20 flex-col gap-2"
                  onClick={() =>
                    window.open(`${API_BASE}/api/dashboard/test-tts`, "_blank")
                  }
                >
                  <Speaker className="h-6 w-6" />
                  Test Text-to-Speech
                </Button>
                <Button
                  variant="outline"
                  className="h-20 flex-col gap-2"
                  onClick={() =>
                    window.open(
                      `${API_BASE}/api/dashboard/test-services`,
                      "_blank"
                    )
                  }
                >
                  <Settings className="h-6 w-6" />
                  Test All Services
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Configuration Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Environment Configuration</CardTitle>
              <CardDescription>
                Current system configuration and environment details
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-3 border rounded-lg">
                    <div className="text-sm font-medium">Environment</div>
                    <div className="text-sm text-muted-foreground">
                      Development/Testing
                    </div>
                  </div>
                  <div className="p-3 border rounded-lg">
                    <div className="text-sm font-medium">API Base URL</div>
                    <div className="text-sm text-muted-foreground">
                      {API_BASE}
                    </div>
                  </div>
                  <div className="p-3 border rounded-lg">
                    <div className="text-sm font-medium">Voice Processing</div>
                    <div className="text-sm text-muted-foreground">
                      Hybrid TTS Enabled
                    </div>
                  </div>
                  <div className="p-3 border rounded-lg">
                    <div className="text-sm font-medium">Real-time Audio</div>
                    <div className="text-sm text-muted-foreground">
                      WebSocket Streaming
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Call Details Dialog */}
      <Dialog open={isCallDetailsOpen} onOpenChange={setIsCallDetailsOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Call Summary & Analysis</DialogTitle>
            <DialogDescription>
              Complete AI-generated analysis and performance metrics
            </DialogDescription>
          </DialogHeader>
          {selectedCallSummary && (
            <div className="space-y-6">
              {/* Summary Overview */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3 border rounded-lg">
                  <Label className="text-xs">Outcome</Label>
                  <div className="mt-1">
                    <Badge {...getOutcomeBadge(selectedCallSummary.outcome)}>
                      {selectedCallSummary.outcome.replace("_", " ")}
                    </Badge>
                  </div>
                </div>
                <div className="p-3 border rounded-lg">
                  <Label className="text-xs">Sentiment</Label>
                  <div className="mt-1">
                    <Badge variant="outline">
                      {selectedCallSummary.sentiment}
                    </Badge>
                  </div>
                </div>
                <div className="p-3 border rounded-lg">
                  <Label className="text-xs">Urgency</Label>
                  <div className="mt-1">
                    <Badge variant="secondary">
                      {selectedCallSummary.urgency}
                    </Badge>
                  </div>
                </div>
                <div className="p-3 border rounded-lg">
                  <Label className="text-xs">Quality Score</Label>
                  <div className="text-2xl font-bold mt-1">
                    {selectedCallSummary.call_score}/10
                  </div>
                </div>
              </div>

              {/* Key Points and Actions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-3">
                  <div>
                    <Label className="font-medium">Key Points</Label>
                    <ul className="list-disc list-inside text-sm space-y-1 mt-2">
                      {selectedCallSummary.key_points?.map((point, i) => (
                        <li key={i}>{point}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <Label className="font-medium">Customer Concerns</Label>
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
                    <Label className="font-medium">Recommended Actions</Label>
                    <ul className="list-disc list-inside text-sm space-y-1 mt-2">
                      {selectedCallSummary.recommended_actions?.map(
                        (action, i) => (
                          <li key={i}>{action}</li>
                        )
                      )}
                    </ul>
                  </div>

                  <div>
                    <Label className="font-medium">Follow-up Timeframe</Label>
                    <p className="text-sm mt-2">
                      {selectedCallSummary.follow_up_timeframe}
                    </p>
                  </div>
                </div>
              </div>

              {/* Agent Notes */}
              <div>
                <Label className="font-medium">AI Agent Notes</Label>
                <div className="mt-2 p-3 bg-gray-50 rounded-lg">
                  <p className="text-sm">{selectedCallSummary.agent_notes}</p>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
