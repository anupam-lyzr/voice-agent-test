import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { Badge } from '../components/ui/badge'
import { 
  Phone, 
  Upload, 
  Play,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  RefreshCw,
//   LucideIcon
} from 'lucide-react'

import  type { LucideIcon } from 'lucide-react'

interface Agent {
  id: string
  name: string
}

interface TestCallState {
  phone: string
  agent: string
  loading: boolean
  result: TestCallResult | null
}

interface TestCallResult {
  success: boolean
  message: string
  callId?: string
}

interface SystemTestsState {
  twilio: TestStatus | null
  database: TestStatus | null
  redis: TestStatus | null
  lyzr: TestStatus | null
  elevenlabs: TestStatus | null
  loading: boolean
}

type TestStatus = 'success' | 'error' | 'warning'

interface SystemTest {
  key: keyof Omit<SystemTestsState, 'loading'>
  name: string
  description: string
}

interface TestFeature {
  name: string
}

interface StatusConfig {
  variant: "default" | "destructive" | "secondary" | "outline"
  text: string
}

export default function Testing() {
  const [testCall, setTestCall] = useState<TestCallState>({
    phone: '+918770217684',
    agent: 'anthony_fracchia',
    loading: false,
    result: null
  })
  
  const [systemTests, setSystemTests] = useState<SystemTestsState>({
    twilio: null,
    database: null,
    redis: null,
    lyzr: null,
    elevenlabs: null,
    loading: false
  })

  const agents: Agent[] = [
    { id: 'anthony_fracchia', name: 'Anthony Fracchia' },
    { id: 'lashawn_boyd', name: 'LaShawn Boyd' },
    { id: 'india_watson', name: 'India Watson' },
    { id: 'hineth_pettway', name: 'Hineth Pettway' },
    { id: 'keith_braswell', name: 'Keith Braswell' }
  ]

  const handleTestCall = async (): Promise<void> => {
    setTestCall(prev => ({ ...prev, loading: true, result: null }))
    
    try {
      const response = await fetch('http://localhost:8000/twilio/voice', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          CallSid: `test-${Date.now()}`,
          CallStatus: 'in-progress',
          From: testCall.phone,
          To: '+15551234567'
        })
      })

      if (response.ok) {
        setTestCall(prev => ({
          ...prev,
          loading: false,
          result: {
            success: true,
            message: 'Test call initiated successfully',
            callId: `test-${Date.now()}`
          }
        }))
      } else {
        throw new Error(`HTTP ${response.status}`)
      }
    } catch (error) {
      setTestCall(prev => ({
        ...prev,
        loading: false,
        result: {
          success: false,
          message: `Test failed: ${error instanceof Error ? error.message : 'Unknown error'}`
        }
      }))
    }
  }

  const runSystemTests = async (): Promise<void> => {
    setSystemTests(prev => ({ ...prev, loading: true }))
    
    const tests = [
      { name: 'twilio', url: '/twilio/voice', method: 'POST' },
      { name: 'database', url: '/health', method: 'GET' },
      { name: 'redis', url: '/health', method: 'GET' },
    ] as const

    const results: Partial<SystemTestsState> = {}
    
    for (const test of tests) {
      try {
        const response = await fetch(`http://localhost:8000${test.url}`, {
          method: test.method,
          headers: test.method === 'POST' ? {
            'Content-Type': 'application/x-www-form-urlencoded'
          } : {}
        })
        
        results[test.name] = response.ok ? 'success' : 'error'
      } catch (error) {
        results[test.name] = 'error'
      }
    }

    // Mock LYZR and ElevenLabs tests
    results.lyzr = 'warning' // Not configured
    results.elevenlabs = 'warning' // Not configured

    setSystemTests(prev => ({ ...prev, ...results, loading: false }))
  }

  const getStatusIcon = (status: TestStatus | null): JSX.Element => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-5 w-5 text-green-600" />
      case 'error':
        return <XCircle className="h-5 w-5 text-red-600" />
      case 'warning':
        return <AlertTriangle className="h-5 w-5 text-yellow-600" />
      default:
        return <Clock className="h-5 w-5 text-gray-400" />
    }
  }

  const getStatusBadge = (status: TestStatus | null): JSX.Element => {
    const variants: Record<TestStatus | 'null', StatusConfig> = {
      success: { variant: "default", text: "Passed" },
      error: { variant: "destructive", text: "Failed" },
      warning: { variant: "secondary", text: "Warning" },
      null: { variant: "outline", text: "Not Tested" }
    }
    
    const config = variants[status || 'null']
    return <Badge variant={config.variant}>{config.text}</Badge>
  }

  const systemTestItems: SystemTest[] = [
    { key: 'twilio', name: 'Twilio Integration', description: 'Voice webhook endpoint' },
    { key: 'database', name: 'Database Connection', description: 'MongoDB connectivity' },
    { key: 'redis', name: 'Redis Cache', description: 'Session storage' },
    { key: 'lyzr', name: 'LYZR Agent API', description: 'AI conversation agent' },
    { key: 'elevenlabs', name: 'ElevenLabs TTS', description: 'Text-to-speech service' }
  ]

  const testFeatures: TestFeature[] = [
    { name: 'Hybrid TTS (Static + Dynamic)' },
    { name: 'Agent Assignment Logic' },
    { name: 'CRM Integration Test' },
    { name: 'Call Summary Generation' },
    { name: 'Latency Measurement' },
    { name: 'Error Handling' },
    { name: 'Voice Quality Testing' },
    { name: 'End-to-End Call Flow' }
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold text-gray-900">Testing & Quality Assurance</h2>
        <p className="text-gray-600">Test voice calls and system integrations</p>
      </div>

      {/* Test Mode Alert */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center space-x-2">
          <CheckCircle className="h-5 w-5 text-blue-600" />
          <span className="font-medium text-blue-900">Test Mode Active</span>
        </div>
        <p className="text-blue-700 mt-1">All calls in this section use test data and will not affect production clients.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quick Call Test */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Phone className="h-5 w-5" />
              <span>Quick Call Test</span>
            </CardTitle>
            <CardDescription>Test voice processing with your phone number</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">Test Phone Number</label>
              <Input
                type="tel"
                value={testCall.phone}
                onChange={(e) => setTestCall(prev => ({ ...prev, phone: e.target.value }))}
                placeholder="+918770217684"
                className="w-full"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Assign to Agent</label>
              <Select value={testCall.agent} onValueChange={(value) => setTestCall(prev => ({ ...prev, agent: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an agent" />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((agent) => (
                    <SelectItem key={agent.id} value={agent.id}>
                      {agent.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button 
              onClick={runSystemTests}
              disabled={systemTests.loading}
              className="w-full"
              variant="outline"
            >
              {systemTests.loading ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Running Tests...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Run All Tests
                </>
              )}
            </Button>

            <div className="space-y-3">
              {systemTestItems.map((test) => (
                <div key={test.key} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center space-x-3">
                    {getStatusIcon(systemTests[test.key])}
                    <div>
                      <p className="font-medium">{test.name}</p>
                      <p className="text-sm text-gray-600">{test.description}</p>
                    </div>
                  </div>
                  {getStatusBadge(systemTests[test.key])}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Test Data Upload */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Upload className="h-5 w-5" />
            <span>Upload Test Client Data</span>
          </CardTitle>
          <CardDescription>Upload CSV file with test client information</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors">
            <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Drop CSV file here</h3>
            <p className="text-gray-600 mb-4">or click to browse files</p>
            <p className="text-sm text-gray-500">
              Required format: first_name, last_name, phone, email, tags
            </p>
            <Button variant="outline" className="mt-4">
              Select File
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Test Features */}
      <Card>
        <CardHeader>
          <CardTitle>Test Coverage</CardTitle>
          <CardDescription>Features tested in this environment</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {testFeatures.map((feature, index) => (
              <div key={index} className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-green-600" />
                <span className="text-sm">{feature.name}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}