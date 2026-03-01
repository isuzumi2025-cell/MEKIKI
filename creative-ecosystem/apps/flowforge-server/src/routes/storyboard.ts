import { Router } from "express";
import { getLLMClient } from "@icc/ai-client";

export const storyboardRouter = Router();

interface ShotProposal {
  shot_no: number;
  phase: string;
  start_sec: number;
  end_sec: number;
  copy_text: string;
  narration_text: string;
  visual_hint: string;
}

interface GenerateRequest {
  plan_id: string;
  shots: ShotProposal[];
  style?: string;
}

/**
 * POST /api/storyboard/generate
 * Takes StoryboardProposal[] from MEKIKI and generates images + video via AI.
 */
storyboardRouter.post("/generate", async (req, res) => {
  const body = req.body as GenerateRequest;
  const { plan_id, shots = [], style = "realistic" } = body;

  if (!plan_id || !shots.length) {
    res.status(400).json({ error: "plan_id and shots are required" });
    return;
  }

  try {
    // Build visual prompts for each shot using Gemini
    const client = getLLMClient("gemini", "gemini-2.0-flash");
    const results = [];

    for (const shot of shots) {
      const promptReq = `
You are a creative director. Generate a detailed visual prompt for a storyboard shot.
Phase: ${shot.phase}
Copy: ${shot.copy_text}
Narration: ${shot.narration_text}
Visual hint: ${shot.visual_hint}
Style: ${style}

Return a single paragraph image generation prompt (no formatting, no bullets).
      `.trim();

      const resp = await client.generate(promptReq);
      results.push({
        shot_no: shot.shot_no,
        phase: shot.phase,
        start_sec: shot.start_sec,
        end_sec: shot.end_sec,
        copy_text: shot.copy_text,
        narration_text: shot.narration_text,
        visual_hint: shot.visual_hint,
        generated_prompt: resp.error ? shot.visual_hint : resp.text,
        image_url: null, // Phase 6: Imagen4 integration
        video_url: null, // Phase 6: Veo3.1 integration
        status: resp.error ? "prompt_failed" : "prompt_ready",
      });
    }

    res.json({
      plan_id,
      results,
      total_shots: shots.length,
      generated_at: new Date().toISOString(),
    });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

/**
 * GET /api/storyboard/jobs/:jobId
 */
storyboardRouter.get("/jobs/:jobId", (req, res) => {
  res.json({ job_id: req.params.jobId, status: "not_found" });
});
