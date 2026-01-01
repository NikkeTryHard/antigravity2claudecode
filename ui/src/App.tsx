import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ErrorBoundary, PageErrorBoundary } from "@/components/ErrorBoundary";
import { Layout } from "@/components/Layout";
import { Dashboard } from "@/pages/Dashboard";
import { Debug } from "@/pages/Debug";
import { Logs } from "@/pages/Logs";
import { Providers } from "@/pages/Providers";
import { Routing } from "@/pages/Routing";
import { Settings } from "@/pages/Settings";
import "./index.css";

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route
              index
              element={
                <PageErrorBoundary pageName="Dashboard">
                  <Dashboard />
                </PageErrorBoundary>
              }
            />
            <Route
              path="providers"
              element={
                <PageErrorBoundary pageName="Providers">
                  <Providers />
                </PageErrorBoundary>
              }
            />
            <Route
              path="routing"
              element={
                <PageErrorBoundary pageName="Routing">
                  <Routing />
                </PageErrorBoundary>
              }
            />
            <Route
              path="logs"
              element={
                <PageErrorBoundary pageName="Logs">
                  <Logs />
                </PageErrorBoundary>
              }
            />
            <Route
              path="debug"
              element={
                <PageErrorBoundary pageName="Debug">
                  <Debug />
                </PageErrorBoundary>
              }
            />
            <Route
              path="settings"
              element={
                <PageErrorBoundary pageName="Settings">
                  <Settings />
                </PageErrorBoundary>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
