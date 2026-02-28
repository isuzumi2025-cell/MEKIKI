import { Router } from "express";

export const statusRouter = Router();

statusRouter.get("/", (_req, res) => {
  res.json({
    status: "ok",
    workers: 0,
    activeJobs: 0,
    capabilities: ["storyboard-plan", "image-gen", "video-gen", "render"],
  });
});
