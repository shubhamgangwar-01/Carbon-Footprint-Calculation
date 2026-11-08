import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import "./index.css";
import Admin from "./pages/Admin";
import Conferences from "./pages/Conferences";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Methodology from "./pages/Methodology";
import Report from "./pages/Report";
import Results from "./pages/Results";
import WhatIf from "./pages/WhatIf";
import Wizard from "./pages/Wizard";
import { ConferenceProvider } from "./state/ConferenceContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ConferenceProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Landing />} />
            <Route path="/calculator" element={<Navigate to="/calculator/basic" replace />} />
            <Route path="/calculator/:step" element={<Wizard />} />
            <Route path="/results/:calcId" element={<Results />} />
            <Route path="/results/:calcId/what-if" element={<WhatIf />} />
            <Route path="/results/:calcId/report" element={<Report />} />
            <Route path="/conferences" element={<Conferences />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route path="/login" element={<Login />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ConferenceProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
