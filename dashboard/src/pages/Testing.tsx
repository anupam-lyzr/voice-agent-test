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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "../components/ui/collapsible";
import {
  Phone,
  User,
  Play,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  ChevronsUpDown,
  RefreshCw,
  Rocket,
  PlusCircle,
} from "lucide-react";

const API_BASE = "http://localhost:8000";

// Interface definitions
interface TestClient {
  id: string;
  name: string;
  phone: string;
}

interface TestAgent {
  id: string;
  name: string;
  email: string;
}

interface CallStep {
  step: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  timestamp?: string;
  details?: any;
  error?: string;
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

  // State for test execution
  const [testClients, setTestClients] = useState<TestClient[]>([]);
  const [testAgents, setTestAgents] = useState<TestAgent[]>([]);
  const [selectedClient, setSelectedClient] = useState("");
  const [selectedAgent, setSelectedAgent] = useState("");
  const [callSteps, setCallSteps] = useState<CallStep[]>([]);
  const [callResult, setCallResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  // Data Fetching
  const loadData = async (type: "clients" | "agents") => {
    try {
      const response = await fetch(`${API_BASE}/api/dashboard/test-${type}`);
      const data = await response.json();
      if (type === "clients") setTestClients(data.clients || []);
      if (type === "agents") setTestAgents(data.agents || []);
    } catch (error) {
      console.error(`Failed to load test ${type}:`, error);
      // Using sonner for error notification
      toast.error(`Failed to load test ${type}`, {
        description: "Please check the API connection and try again.",
      });
    }
  };

  useEffect(() => {
    loadData("clients");
    loadData("agents");
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
        // Using sonner for success notification
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
        // Using sonner for error notification
        toast.error("Error creating client", {
          description: result.detail || "Failed to create client.",
        });
      }
    } catch (error) {
      // Using sonner for error notification
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
        // Using sonner for success notification
        toast.success(result.message);
        setNewAgent({
          name: "",
          email: "",
          google_calendar_id: "",
          timezone: "America/New_York",
        });
        loadData("agents");
      } else {
        // Using sonner for error notification
        toast.error("Error creating agent", {
          description: result.detail || "Failed to create agent.",
        });
      }
    } catch (error) {
      // Using sonner for error notification
      toast.error("An unexpected error occurred.");
    }
    setIsCreatingAgent(false);
  };

  const handleStartTestCall = async () => {
    if (!selectedClient || !selectedAgent) return;
    setIsCallInProgress(true);
    setCallResult(null);
    setCallSteps([]);

    try {
      const response = await fetch(`${API_BASE}/api/dashboard/test-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: selectedClient,
          agent_id: selectedAgent,
          simulation_mode: true,
        }),
      });
      const result = await response.json();
      if (result.success) {
        pollCallStatus(result.call_id);
      } else {
        setCallResult({
          success: false,
          message: result.detail || "Failed to start test call.",
        });
        setIsCallInProgress(false);
      }
    } catch (error) {
      setCallResult({
        success: false,
        message: "An unexpected error occurred.",
      });
      setIsCallInProgress(false);
    }
  };

  const pollCallStatus = async (callId: string) => {
    const steps = [
      "call_initiated",
      "twilio_connection",
      "voice_processing",
      "customer_response",
      "outcome_determination",
      "call_completed",
    ];

    // Simulate the call flow steps
    for (let i = 0; i < steps.length; i++) {
      await new Promise((resolve) => setTimeout(resolve, 2000)); // 2 second delay

      setCallSteps((prev) => [
        ...prev,
        {
          step: steps[i],
          status: "completed",
          timestamp: new Date().toISOString(),
          details: { step_number: i + 1 },
        },
      ]);
    }

    // Final result
    setCallResult({
      success: true,
      message: "Test call completed successfully! Check call logs for details.",
    });
    setIsCallInProgress(false);

    // Show success message
    toast.success("Test call completed", {
      description: "The test call has been processed successfully.",
    });

    // Refresh client data to show updated status
    loadData("clients");
  };

  const getStepIcon = (status: string) => {
    const iconClass = "h-5 w-5";
    switch (status) {
      case "completed":
        return <CheckCircle className={`${iconClass} text-green-500`} />;
      case "failed":
        return <XCircle className={`${iconClass} text-red-500`} />;
      case "in_progress":
        return (
          <Loader2 className={`${iconClass} text-blue-500 animate-spin`} />
        );
      default:
        return <Clock className={`${iconClass} text-gray-400`} />;
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Voice Agent Testing
        </h1>
        <p className="text-muted-foreground mt-1">
          Create test entities and run end-to-end simulated call flows.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Left Column: Forms for creating test data */}
        <div className="space-y-8">
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
                      setNewClient({ ...newClient, first_name: e.target.value })
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
                      setNewClient({ ...newClient, last_name: e.target.value })
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
                  placeholder="e.g., Interested in PPO plans."
                />
              </div>
              <Button
                onClick={handleCreateClient}
                disabled={
                  isCreatingClient || !newClient.first_name || !newClient.phone
                }
              >
                {isCreatingClient ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <PlusCircle className="mr-2 h-4 w-4" />
                )}
                Create Client
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
              <Button
                onClick={handleCreateAgent}
                disabled={isCreatingAgent || !newAgent.name || !newAgent.email}
              >
                {isCreatingAgent ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <PlusCircle className="mr-2 h-4 w-4" />
                )}
                Create Agent
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Test execution and results */}
        <Card className="sticky top-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Phone className="h-5 w-5" /> Run Test Call
            </CardTitle>
            <CardDescription>
              Select a client and agent to run a simulated call flow.
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
                      <SelectValue placeholder="Select a client" />
                    </SelectTrigger>
                    <SelectContent>
                      {testClients.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name}
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
                      <SelectValue placeholder="Select an agent" />
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

            <Button
              onClick={handleStartTestCall}
              disabled={isCallInProgress || !selectedClient || !selectedAgent}
              className="w-full"
            >
              {isCallInProgress ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              {isCallInProgress
                ? "Call in Progress..."
                : "Start Test Call Flow"}
            </Button>

            {callResult && !callResult.success && (
              <div className="text-sm text-red-600 p-3 bg-red-50 rounded-md">
                {callResult.message}
              </div>
            )}

            {callSteps.length > 0 && (
              <div className="space-y-3 pt-4">
                <h4 className="font-medium text-sm">Call Progress</h4>
                {callSteps.map((step, index) => (
                  <Collapsible key={index} className="border p-3 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {getStepIcon(step.status)}
                        <span className="font-medium capitalize">
                          {step.step.replace(/_/g, " ")}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge
                          variant={
                            step.status === "completed"
                              ? "default"
                              : step.status === "failed"
                              ? "destructive"
                              : "secondary"
                          }
                        >
                          {step.status}
                        </Badge>
                        {(step.details || step.error) && (
                          <CollapsibleTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="w-9 p-0"
                            >
                              <ChevronsUpDown className="h-4 w-4" />
                              <span className="sr-only">Toggle</span>
                            </Button>
                          </CollapsibleTrigger>
                        )}
                      </div>
                    </div>
                    {(step.details || step.error) && (
                      <CollapsibleContent className="text-xs text-muted-foreground space-y-2 pt-3 mt-3 border-t">
                        {step.details &&
                          Object.keys(step.details).length > 0 && (
                            <pre className="p-2 bg-slate-50 rounded-md whitespace-pre-wrap">
                              {JSON.stringify(step.details, null, 2)}
                            </pre>
                          )}
                        {step.error && (
                          <div className="text-red-500 p-2 bg-red-50 rounded-md">
                            Error: {step.error}
                          </div>
                        )}
                      </CollapsibleContent>
                    )}
                  </Collapsible>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
