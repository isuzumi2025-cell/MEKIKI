import { Router } from "express";

export const renderRouter = Router();

/**
 * POST /api/render/mp4
 * Remotion render pipeline (Phase 6 implementation)
 */
renderRouter.post("/mp4", (_req, res) => {
  res.status(501).json({
    error: "Remotion render not yet configured",
    hint: "Phase 6: npm i @remotion/cli and configure compositions",
  });
});

/**
 * GET /api/render/status/:jobId
 */
renderRouter.get("/status/:jobId", (req, res) => {
  res.json({ job_id: req.params.jobId, status: "unknown" });
});
