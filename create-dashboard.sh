#!/bin/bash
# create-dashboard.sh
# Create the dashboard structure with production and testing features

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🖥️ Creating Voice Agent Dashboard${NC}"

# Create dashboard directory structure
echo -e "${YELLOW}📁 Creating dashboard structure...${NC}"

mkdir -p dashboard/public
mkdir -p dashboard/src/{components,pages,services,utils,hooks}
mkdir -p dashboard/src/components/{common,campaign,testing,agents,clients}

# Create package.json
echo -e "${YELLOW}📦 Creating package.json...${NC}"
cat > dashboard/package.json << 'EOF'
{
  "name": "voice-agent-dashboard",
  "version": "1.0.0",
  "description": "Voice Agent Campaign Management Dashboard",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1",
    "react-router-dom": "^6.8.0",
    "axios": "^1.3.0",
    "recharts": "^2.5.0",
    "@mui/material": "^5.11.0",
    "@mui/icons-material": "^5.11.0",
    "@emotion/react": "^11.10.0",
    "@emotion/styled": "^11.10.0",
    "date-fns": "^2.29.0",
    "react-query": "^3.39.0",
    "socket.io-client": "^4.6.0"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "eslintConfig": {
    "extends": [
      "react-app"
    ]
  },
  "browserslist": {
    "production": [
      ">0.2%",
      "not dead",
      "not op_mini all"
    ],
    "development": [
      "last 1 chrome version",
      "last 1 firefox version",
      "last 1 safari version"
    ]
  }
}
EOF

# Create public/index.html
cat > dashboard/public/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%PUBLIC_URL%/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="Voice Agent Campaign Management Dashboard" />
    <title>Voice Agent Dashboard</title>
    <style>
      body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
          'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
          sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
      }
    </style>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
EOF

# Create main App.js
cat > dashboard/src/App.js << 'EOF'
import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { QueryClient, QueryClientProvider } from 'react-query';

// Pages
import Dashboard from './pages/Dashboard';
import CampaignManager from './pages/CampaignManager';
import Testing from './pages/Testing';
import Analytics from './pages/Analytics';
import ClientManager from './pages/ClientManager';
import AgentManager from './pages/AgentManager';
import Settings from './pages/Settings';

// Components
import Layout from './components/common/Layout';

// Create theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

// Create query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Router>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/campaign" element={<CampaignManager />} />
              <Route path="/testing" element={<Testing />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/clients" element={<ClientManager />} />
              <Route path="/agents" element={<AgentManager />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Layout>
        </Router>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
EOF

# Create Layout component
cat > dashboard/src/components/common/Layout.js << 'EOF'
import React, { useState } from 'react';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  Divider,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Switch,
  FormControlLabel,
  Chip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Campaign as CampaignIcon,
  Science as TestingIcon,
  Analytics as AnalyticsIcon,
  People as ClientsIcon,
  SupervisorAccount as AgentsIcon,
  Settings as SettingsIcon,
  Phone as PhoneIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

const drawerWidth = 280;

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Campaign Manager', icon: <CampaignIcon />, path: '/campaign' },
  { text: 'Testing & QA', icon: <TestingIcon />, path: '/testing' },
  { text: 'Analytics', icon: <AnalyticsIcon />, path: '/analytics' },
  { text: 'Client Manager', icon: <ClientsIcon />, path: '/clients' },
  { text: 'Agent Manager', icon: <AgentsIcon />, path: '/agents' },
  { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
];

export default function Layout({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [productionMode, setProductionMode] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleModeChange = (event) => {
    setProductionMode(event.target.checked);
    // Store in localStorage for persistence
    localStorage.setItem('productionMode', event.target.checked);
  };

  const drawer = (
    <div>
      <Toolbar>
        <PhoneIcon sx={{ mr: 2 }} />
        <Typography variant="h6" noWrap>
          Voice Agent
        </Typography>
      </Toolbar>
      <Divider />
      
      {/* Production/Test Mode Toggle */}
      <Box sx={{ p: 2 }}>
        <FormControlLabel
          control={
            <Switch
              checked={productionMode}
              onChange={handleModeChange}
              color="warning"
            />
          }
          label={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2">
                {productionMode ? 'Production' : 'Test'} Mode
              </Typography>
              <Chip 
                label={productionMode ? 'LIVE' : 'TEST'} 
                size="small" 
                color={productionMode ? 'error' : 'success'}
                variant="outlined"
              />
            </Box>
          }
        />
      </Box>
      <Divider />

      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => navigate(item.path)}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </div>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          ml: { sm: `${drawerWidth}px` },
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Voice Agent Campaign Dashboard
          </Typography>
          
          {/* Live Status Indicator */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Chip 
              label={`${productionMode ? 'PRODUCTION' : 'TESTING'}`}
              color={productionMode ? 'error' : 'success'}
              variant="filled"
              size="small"
            />
            <Chip 
              label="● LIVE"
              color="success"
              variant="outlined"
              size="small"
            />
          </Box>
        </Toolbar>
      </AppBar>

      <Box
        component="nav"
        sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{ 
          flexGrow: 1, 
          p: 3, 
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          mt: 8
        }}
      >
        {children}
      </Box>
    </Box>
  );
}
EOF

# Create Dashboard page
cat > dashboard/src/pages/Dashboard.js << 'EOF'
import React from 'react';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  LinearProgress,
} from '@mui/material';
import {
  Phone as PhoneIcon,
  People as PeopleIcon,
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';

// Components
import StatsCard from '../components/common/StatsCard';
import CampaignProgress from '../components/campaign/CampaignProgress';
import RecentCalls from '../components/campaign/RecentCalls';
import AgentStatus from '../components/agents/AgentStatus';

export default function Dashboard() {
  // Mock data - will be replaced with real API calls
  const stats = {
    totalCalls: 1247,
    completedCalls: 892,
    interestedClients: 178,
    scheduledMeetings: 156,
  };

  const completionRate = (stats.completedCalls / stats.totalCalls) * 100;
  const interestRate = (stats.interestedClients / stats.completedCalls) * 100;

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Campaign Dashboard
      </Typography>
      
      <Grid container spacing={3}>
        {/* Stats Cards */}
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Total Calls"
            value={stats.totalCalls.toLocaleString()}
            icon={<PhoneIcon />}
            color="primary"
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Completed Calls"
            value={stats.completedCalls.toLocaleString()}
            subtitle={`${completionRate.toFixed(1)}% completion rate`}
            icon={<PeopleIcon />}
            color="success"
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Interested Clients"
            value={stats.interestedClients.toLocaleString()}
            subtitle={`${interestRate.toFixed(1)}% interest rate`}
            icon={<TrendingUpIcon />}
            color="warning"
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Scheduled Meetings"
            value={stats.scheduledMeetings.toLocaleString()}
            icon={<ScheduleIcon />}
            color="info"
          />
        </Grid>

        {/* Campaign Progress */}
        <Grid item xs={12} md={8}>
          <CampaignProgress />
        </Grid>

        {/* Agent Status */}
        <Grid item xs={12} md={4}>
          <AgentStatus />
        </Grid>

        {/* Recent Calls */}
        <Grid item xs={12}>
          <RecentCalls />
        </Grid>
      </Grid>
    </Box>
  );
}
EOF

# Create Testing page
cat > dashboard/src/pages/Testing.js << 'EOF'
import React, { useState } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Card,
  CardContent,
  Button,
  TextField,
  Grid,
  Chip,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Upload as UploadIcon,
  Phone as PhoneIcon,
  Science as TestIcon,
} from '@mui/icons-material';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`testing-tabpanel-${index}`}
      aria-labelledby={`testing-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

export default function Testing() {
  const [tabValue, setTabValue] = useState(0);
  const [testPhone, setTestPhone] = useState('');
  const [selectedAgent, setSelectedAgent] = useState('');
  const [testResult, setTestResult] = useState(null);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const handleTestCall = () => {
    // Mock test call - will be replaced with actual API call
    setTestResult({
      status: 'success',
      message: 'Test call initiated successfully',
      callId: 'test-' + Date.now(),
    });
  };

  const agents = [
    { id: 'anthony_fracchia', name: 'Anthony Fracchia' },
    { id: 'lashawn_boyd', name: 'LaShawn Boyd' },
    { id: 'india_watson', name: 'India Watson' },
    { id: 'hineth_pettway', name: 'Hineth Pettway' },
    { id: 'keith_braswell', name: 'Keith Braswell' },
  ];

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Testing & Quality Assurance
      </Typography>

      <Alert severity="info" sx={{ mb: 3 }}>
        <strong>Test Mode Active:</strong> All calls in this section use test data and will not affect production clients.
      </Alert>

      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label="Quick Call Test" icon={<PhoneIcon />} />
            <Tab label="Upload Test Data" icon={<UploadIcon />} />
            <Tab label="Voice Quality Test" icon={<TestIcon />} />
            <Tab label="Integration Tests" icon={<PlayIcon />} />
          </Tabs>
        </Box>

        {/* Quick Call Test */}
        <TabPanel value={tabValue} index={0}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Test Call Configuration
                </Typography>
                
                <TextField
                  label="Test Phone Number"
                  value={testPhone}
                  onChange={(e) => setTestPhone(e.target.value)}
                  fullWidth
                  margin="normal"
                  placeholder="+1234567890"
                  helperText="Your phone number for testing"
                />

                <FormControl fullWidth margin="normal">
                  <InputLabel>Assign to Agent</InputLabel>
                  <Select
                    value={selectedAgent}
                    onChange={(e) => setSelectedAgent(e.target.value)}
                    label="Assign to Agent"
                  >
                    {agents.map((agent) => (
                      <MenuItem key={agent.id} value={agent.id}>
                        {agent.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <Box sx={{ mt: 3 }}>
                  <Button
                    variant="contained"
                    size="large"
                    startIcon={<PhoneIcon />}
                    onClick={handleTestCall}
                    disabled={!testPhone || !selectedAgent}
                  >
                    Start Test Call
                  </Button>
                </Box>

                {testResult && (
                  <Alert 
                    severity={testResult.status === 'success' ? 'success' : 'error'} 
                    sx={{ mt: 2 }}
                  >
                    {testResult.message}
                    {testResult.callId && (
                      <Box component="span" sx={{ display: 'block', mt: 1 }}>
                        <Chip label={`Call ID: ${testResult.callId}`} size="small" />
                      </Box>
                    )}
                  </Alert>
                )}
              </CardContent>
            </Grid>

            <Grid item xs={12} md={6}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Test Call Features
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Chip label="✓ Hybrid TTS (Static + Dynamic)" variant="outlined" />
                  <Chip label="✓ Agent Assignment Logic" variant="outlined" />
                  <Chip label="✓ CRM Integration Test" variant="outlined" />
                  <Chip label="✓ Call Summary Generation" variant="outlined" />
                  <Chip label="✓ Latency Measurement" variant="outlined" />
                  <Chip label="✓ Error Handling" variant="outlined" />
                </Box>
              </CardContent>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Upload Test Data */}
        <TabPanel value={tabValue} index={1}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Upload Test Client Data
            </Typography>
            
            <Alert severity="warning" sx={{ mb: 2 }}>
              Test data will be marked as test clients and processed separately from production data.
            </Alert>

            <Box sx={{ border: '2px dashed #ccc', borderRadius: 2, p: 4, textAlign: 'center' }}>
              <UploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Drop CSV file here or click to browse
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Supported format: first_name, last_name, phone, email, tags
              </Typography>
              <Button variant="outlined" sx={{ mt: 2 }}>
                Select File
              </Button>
            </Box>
          </CardContent>
        </TabPanel>

        {/* Voice Quality Test */}
        <TabPanel value={tabValue} index={2}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Voice Quality & Latency Testing
            </Typography>
            
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Button variant="outlined" fullWidth>
                  Test Static TTS Response
                </Button>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Button variant="outlined" fullWidth>
                  Test Dynamic TTS Response
                </Button>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Button variant="outlined" fullWidth>
                  Test Speech Recognition
                </Button>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Button variant="outlined" fullWidth>
                  Test End-to-End Latency
                </Button>
              </Grid>
            </Grid>
          </CardContent>
        </TabPanel>

        {/* Integration Tests */}
        <TabPanel value={tabValue} index={3}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              System Integration Tests
            </Typography>
            
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Button variant="outlined" startIcon={<TestIcon />}>
                Test Database Connection
              </Button>
              <Button variant="outlined" startIcon={<TestIcon />}>
                Test Redis Cache
              </Button>
              <Button variant="outlined" startIcon={<TestIcon />}>
                Test Twilio Integration
              </Button>
              <Button variant="outlined" startIcon={<TestIcon />}>
                Test LYZR Agent API
              </Button>
              <Button variant="outlined" startIcon={<TestIcon />}>
                Test Capsule CRM
              </Button>
              <Button variant="outlined" startIcon={<TestIcon />}>
                Test Google Calendar
              </Button>
              <Button variant="outlined" startIcon={<TestIcon />}>
                Test Email Notifications
              </Button>
            </Box>
          </CardContent>
        </TabPanel>
      </Card>
    </Box>
  );
}
EOF

# Create index.js
cat > dashboard/src/index.js << 'EOF'
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
EOF

# Create StatsCard component
cat > dashboard/src/components/common/StatsCard.js << 'EOF'
import React from 'react';
import { Card, CardContent, Typography, Box, Avatar } from '@mui/material';

export default function StatsCard({ title, value, subtitle, icon, color = 'primary' }) {
  const getColorCode = (color) => {
    const colors = {
      primary: '#1976d2',
      success: '#2e7d32',
      warning: '#ed6c02',
      error: '#d32f2f',
      info: '#0288d1',
    };
    return colors[color] || colors.primary;
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box>
            <Typography color="textSecondary" gutterBottom variant="body2">
              {title}
            </Typography>
            <Typography variant="h4" component="div">
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="body2" color="textSecondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          <Avatar sx={{ bgcolor: getColorCode(color), width: 56, height: 56 }}>
            {icon}
          </Avatar>
        </Box>
      </CardContent>
    </Card>
  );
}
EOF

echo -e "${GREEN}✅ Dashboard structure created!${NC}"
echo
echo -e "${BLUE}📂 Dashboard Structure:${NC}"
echo "├── dashboard/"
echo "├── ├── public/index.html"
echo "├── ├── src/"
echo "├── ├── ├── App.js"
echo "├── ├── ├── index.js"
echo "├── ├── ├── pages/"
echo "├── ├── ├── ├── Dashboard.js"
echo "├── ├── ├── ├── Testing.js"
echo "├── ├── ├── └── [Other pages...]"
echo "├── ├── ├── components/"
echo "├── ├── ├── ├── common/Layout.js"
echo "├── ├── ├── ├── common/StatsCard.js"
echo "├── ├── └── └── [Other components...]"
echo "└── └── package.json"
echo
echo -e "${YELLOW}🚀 Next Steps:${NC}"
echo "1. cd dashboard && npm install"
echo "2. npm start  # Start development server"
echo "3. Dashboard will be available at http://localhost:3000"