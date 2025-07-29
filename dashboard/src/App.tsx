import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Testing from "./pages/Testing";
import { Toaster } from "sonner";
function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/testing" element={<Testing />} />
        </Routes>
      </Layout>
      <Toaster position="top-right" richColors />
    </Router>
  );
}

export default App;
