import express from "express";
import cors from "cors";
import { storyboardRouter } from "./routes/storyboard.js";
import { renderRouter } from "./routes/render.js";
import { statusRouter } from "./routes/status.js";

const app = express();
const PORT = process.env.PORT ?? 3001;

app.use(cors({ origin: ["http://localhost:5173", "http://localhost:8000"] }));
app.use(express.json({ limit: "50mb" }));

// Routes
app.use("/api/status", statusRouter);
app.use("/api/storyboard", storyboardRouter);
app.use("/api/render", renderRouter);

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "flowforge-server", version: "0.1.0" });
});

app.listen(PORT, () => {
  console.log(`🎬 FlowForge Server running on http://localhost:${PORT}`);
});

export { app };
