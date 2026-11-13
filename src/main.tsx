import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./style.css";

const mount = document.getElementById("root");
if (!mount) throw new Error("Missing app root");
createRoot(mount).render(<React.StrictMode><App /></React.StrictMode>);
