import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { AppProviders } from "@/app/providers";
import { AppRoutes } from "@/app/router";
import "./index.css";

const container = document.getElementById("root");
if (!container) throw new Error("Root-Element #root fehlt in index.html.");

createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <AppProviders>
        <AppRoutes />
      </AppProviders>
    </BrowserRouter>
  </StrictMode>,
);
