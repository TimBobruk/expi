import "@/App.css";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import PayTable from "@/pages/PayTable";
import ManagerDashboard from "@/pages/ManagerDashboard";
import { Toaster } from "@/components/ui/sonner";

function AdminRoute() {
  const navigate = useNavigate();
  return <ManagerDashboard onBack={() => navigate("/")} />;
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<PayTable />} />
          <Route path="/admin" element={<AdminRoute />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" richColors />
    </div>
  );
}

export default App;