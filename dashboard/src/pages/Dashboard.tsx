import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { 
  Phone, 
  Users, 
  TrendingUp, 
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  RefreshCw,
//   LucideIcon
} from 'lucide-react'
import  type { LucideIcon } from 'lucide-react'


import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface DashboardStats {
  totalCalls: number
  completedCalls: number
  interestedClients: number
  scheduledMeetings: number
  loading: boolean
}

interface RecentCall {
  id: number
  clientName: string
  phone: string
  outcome: 'interested' | 'not_interested' | 'no_answer'
  agent: string
  time: string
}

interface AgentStat {
  name: string
  calls: number
  interested: number
  online: boolean
}

interface ChartData {
  name: string
  calls: number
  interested: number
}

interface StatCardProps {
  title: string
  value: number
  subtitle?: string
  icon: LucideIcon
  color?: string
}

interface OutcomeBadgeConfig {
  variant: "default" | "secondary" | "outline"
  icon: LucideIcon
  text: string
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    totalCalls: 0,
    completedCalls: 0,
    interestedClients: 0,
    scheduledMeetings: 0,
    loading: true
  })

  const [recentCalls, setRecentCalls] = useState<RecentCall[]>([])
  const [agentStats, setAgentStats] = useState<AgentStat[]>([])

  // Mock data for demo
  const chartData: ChartData[] = [
    { name: 'Mon', calls: 45, interested: 12 },
    { name: 'Tue', calls: 52, interested: 15 },
    { name: 'Wed', calls: 38, interested: 8 },
    { name: 'Thu', calls: 61, interested: 18 },
    { name: 'Fri', calls: 55, interested: 14 },
    { name: 'Sat', calls: 28, interested: 6 },
    { name: 'Sun', calls: 33, interested: 9 },
  ]

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async (): Promise<void> => {
    try {
      // Fetch from API
      const response = await fetch('http://localhost:8000/health')
      
      // Mock data for now
      setStats({
        totalCalls: 1247,
        completedCalls: 892,
        interestedClients: 178,
        scheduledMeetings: 156,
        loading: false
      })

      setRecentCalls([
        {
          id: 1,
          clientName: 'Anup Parashar',
          phone: '+918770217684',
          outcome: 'interested',
          agent: 'Anthony Fracchia',
          time: '2 minutes ago'
        },
        {
          id: 2,
          clientName: 'Test Client',
          phone: '+918959084763',
          outcome: 'not_interested',
          agent: 'LaShawn Boyd',
          time: '5 minutes ago'
        },
        {
          id: 3,
          clientName: 'John Smith',
          phone: '+15551234567',
          outcome: 'interested',
          agent: 'India Watson',
          time: '8 minutes ago'
        }
      ])

      setAgentStats([
        { name: 'Anthony Fracchia', calls: 45, interested: 12, online: true },
        { name: 'LaShawn Boyd', calls: 38, interested: 9, online: true },
        { name: 'India Watson', calls: 52, interested: 15, online: false },
        { name: 'Hineth Pettway', calls: 33, interested: 8, online: true },
        { name: 'Keith Braswell', calls: 41, interested: 11, online: true }
      ])

    } catch (error) {
      console.error('Failed to fetch dashboard data:', error)
      setStats(prev => ({ ...prev, loading: false }))
    }
  }

  const StatCard = ({ title, value, subtitle, icon: Icon, color = "blue" }: StatCardProps) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className={`h-4 w-4 text-${color}-600`} />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value.toLocaleString()}</div>
        {subtitle && (
          <p className="text-xs text-gray-600 mt-1">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  )

  const getOutcomeBadge = (outcome: RecentCall['outcome']) => {
    const variants: Record<RecentCall['outcome'], OutcomeBadgeConfig> = {
      interested: { variant: "default", icon: CheckCircle, text: "Interested" },
      not_interested: { variant: "secondary", icon: XCircle, text: "Not Interested" },
      no_answer: { variant: "outline", icon: Clock, text: "No Answer" }
    }
    
    const config = variants[outcome]
    const Icon = config.icon

    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {config.text}
      </Badge>
    )
  }

  if (stats.loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-blue-600" />
        <span className="ml-2 text-lg">Loading dashboard...</span>
      </div>
    )
  }

  const completionRate = ((stats.completedCalls / stats.totalCalls) * 100).toFixed(1)
  const interestRate = ((stats.interestedClients / stats.completedCalls) * 100).toFixed(1)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Campaign Overview</h2>
          <p className="text-gray-600">Real-time voice agent campaign statistics</p>
        </div>
        <Button onClick={fetchDashboardData} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Calls"
          value={stats.totalCalls}
          icon={Phone}
          color="blue"
        />
        <StatCard
          title="Completed Calls"
          value={stats.completedCalls}
          subtitle={`${completionRate}% completion rate`}
          icon={Users}
          color="green"
        />
        <StatCard
          title="Interested Clients"
          value={stats.interestedClients}
          subtitle={`${interestRate}% interest rate`}
          icon={TrendingUp}
          color="yellow"
        />
        <StatCard
          title="Scheduled Meetings"
          value={stats.scheduledMeetings}
          icon={Calendar}
          color="purple"
        />
      </div>

      {/* Charts and Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Call Performance Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Weekly Performance</CardTitle>
            <CardDescription>Calls made vs interested clients</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="calls" fill="#3b82f6" name="Total Calls" />
                <Bar dataKey="interested" fill="#10b981" name="Interested" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Agent Performance */}
        <Card>
          <CardHeader>
            <CardTitle>Agent Performance</CardTitle>
            <CardDescription>Today's agent statistics</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {agentStats.map((agent, index) => (
                <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center space-x-3">
                    <div className={`w-3 h-3 rounded-full ${agent.online ? 'bg-green-500' : 'bg-gray-400'}`} />
                    <div>
                      <p className="font-medium">{agent.name}</p>
                      <p className="text-sm text-gray-600">{agent.calls} calls today</p>
                    </div>
                  </div>
                  <Badge variant="outline">
                    {agent.interested} interested
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Calls */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Calls</CardTitle>
          <CardDescription>Latest call activity</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {recentCalls.map((call) => (
              <div key={call.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50">
                <div className="flex items-center space-x-4">
                  <div>
                    <p className="font-medium">{call.clientName}</p>
                    <p className="text-sm text-gray-600">{call.phone}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="text-right">
                    <p className="text-sm font-medium">{call.agent}</p>
                    <p className="text-xs text-gray-500">{call.time}</p>
                  </div>
                  {getOutcomeBadge(call.outcome)}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}