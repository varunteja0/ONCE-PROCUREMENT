import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "../popup/popup.css";

function mount(): void {
  const host = document.getElementById("root");
  if (!host) throw new Error("options: #root not found");
  const root = createRoot(host);
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

mount();
