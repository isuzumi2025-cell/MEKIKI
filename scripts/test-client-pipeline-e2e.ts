/**
 * test-client-pipeline-e2e.ts — Client Material Pipeline E2E テスト
 *
 * ディレクトリスキャン → 素材解析 → スタイルプロファイル → プロンプト生成
 *
 * 実行: npx tsx scripts/test-client-pipeline-e2e.ts
 * 環境変数: GEMINI_API_KEY が必要
 */

import * as fs from "fs";
import * as path from "path";
import {
  ClientMaterialPipeline,
  type MaterialFile,
  type StyleProfile,
} from "../src/lib/client-material-pipeline.js";

function createTestPng(width: number, height: number): Buffer {
  const buf = Buffer.alloc(57);
  buf[0] = 0x89;
  buf.write("PNG", 1, "ascii");
  buf[4] = 0x0d;
  buf[5] = 0x0a;
  buf[6] = 0x1a;
  buf[7] = 0x0a;
  buf.writeUInt32BE(0x0000000d, 8);
  buf.write("IHDR", 12, "ascii");
  buf.writeUInt32BE(width, 16);
  buf.writeUInt32BE(height, 20);
  buf[24] = 0x08;
  buf[25] = 0x02;
  return buf;
}

(async () => {
  let passed = 0;
  let failed = 0;
  const results: string[] = [];

  function check(name: string, fn: () => void): void {
    try {
      fn();
      results.push("PASS " + name);
      passed++;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      results.push("FAIL " + name + ": " + msg);
      failed++;
    }
  }

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    console.error("GEMINI_API_KEY が設定されていません。");
    console.error("export GEMINI_API_KEY=your-key を実行してください。");
    process.exit(1);
  }

  console.log("=== Client Material Pipeline E2E テスト ===\n");

  const tmpDir = fs.mkdtempSync(path.join("/tmp", "cmp-e2e-"));

  try {
    // === テスト素材準備 ===
    console.log("--- テスト素材準備 ---");

    const imgDir = path.join(tmpDir, "images");
    const subDir = path.join(tmpDir, "images", "sub");
    fs.mkdirSync(imgDir, { recursive: true });
    fs.mkdirSync(subDir, { recursive: true });

    fs.writeFileSync(path.join(imgDir, "hero.png"), createTestPng(1920, 1080));
    fs.writeFileSync(path.join(imgDir, "portrait.png"), createTestPng(1080, 1920));
    fs.writeFileSync(path.join(imgDir, "square.png"), createTestPng(1000, 1000));
    fs.writeFileSync(path.join(subDir, "nested.jpg"), Buffer.from("fake-jpg"));
    fs.writeFileSync(path.join(tmpDir, "doc.pdf"), Buffer.from("%PDF-1.4 test"));
    fs.writeFileSync(path.join(tmpDir, "clip.mp4"), Buffer.from("fake-mp4"));
    fs.writeFileSync(path.join(tmpDir, "readme.txt"), "skip me");
    fs.writeFileSync(path.join(tmpDir, ".hidden.png"), createTestPng(100, 100));

    console.log(`  テストディレクトリ: ${tmpDir}`);

    // === 1. ディレクトリスキャン ===
    console.log("\n--- 1. ディレクトリスキャン ---");

    const pipeline = new ClientMaterialPipeline({ apiKey });
    const files = await pipeline.scanDirectory(tmpDir);

    console.log(`  検出ファイル数: ${files.length}`);
    for (const f of files) {
      console.log(`    ${f.type}: ${f.name} (${f.sizeBytes} bytes)`);
    }

    check("Scan: ファイル検出数 = 6", () => {
      if (files.length !== 6) throw new Error("count=" + files.length);
    });

    check("Scan: 画像ファイル検出", () => {
      const images = files.filter((f) => f.type === "image");
      if (images.length !== 4) throw new Error("images=" + images.length);
    });

    check("Scan: PDF ファイル検出", () => {
      const pdfs = files.filter((f) => f.type === "pdf");
      if (pdfs.length !== 1) throw new Error("pdfs=" + pdfs.length);
    });

    check("Scan: 動画ファイル検出", () => {
      const videos = files.filter((f) => f.type === "video");
      if (videos.length !== 1) throw new Error("videos=" + videos.length);
    });

    check("Scan: テキストファイルは除外", () => {
      const txt = files.filter((f) => f.name === "readme.txt");
      if (txt.length !== 0) throw new Error("txt not excluded");
    });

    check("Scan: 隠しファイルは除外", () => {
      const hidden = files.filter((f) => f.name === ".hidden.png");
      if (hidden.length !== 0) throw new Error("hidden not excluded");
    });

    check("Scan: サブディレクトリの再帰スキャン", () => {
      const nested = files.filter((f) => f.name === "nested.jpg");
      if (nested.length !== 1) throw new Error("nested not found");
    });

    // === 2. 素材解析 (Gemini Vision API) ===
    console.log("\n--- 2. 素材解析 (Gemini Vision API) ---");

    const imageFiles = files.filter((f) => f.type === "image");
    const analyses = await pipeline.analyzeMaterials(imageFiles);

    console.log(`  解析結果数: ${analyses.length}`);
    for (const a of analyses) {
      console.log(`    ${a.file.name}: ${a.description.slice(0, 50)}...`);
      console.log(`      colors: ${a.dominantColors.join(", ")}`);
      console.log(`      style: ${a.style}, mood: ${a.mood}`);
      console.log(`      aspectRatio: ${a.aspectRatio.width}x${a.aspectRatio.height}`);
    }

    check("Analyze: 全画像が解析された", () => {
      if (analyses.length !== imageFiles.length) {
        throw new Error(`analyses=${analyses.length}, expected=${imageFiles.length}`);
      }
    });

    check("Analyze: description が空でない", () => {
      for (const a of analyses) {
        if (!a.description || a.description.length === 0) {
          throw new Error("empty description for " + a.file.name);
        }
      }
    });

    check("Analyze: aspectRatio が正の数", () => {
      for (const a of analyses) {
        if (a.aspectRatio.width <= 0 || a.aspectRatio.height <= 0) {
          throw new Error("invalid aspectRatio for " + a.file.name);
        }
      }
    });

    // === 3. スタイルプロファイル生成 ===
    console.log("\n--- 3. スタイルプロファイル生成 ---");

    const profile = pipeline.generateStyleProfile(analyses);

    console.log(`  dominantColors: ${profile.dominantColors.join(", ")}`);
    console.log(`  dominantStyle: ${profile.dominantStyle}`);
    console.log(`  dominantMood: ${profile.dominantMood}`);
    console.log(`  dominantAspectRatio: ${profile.dominantAspectRatio}`);
    console.log(`  brandElements: ${profile.brandElements.join(", ") || "(なし)"}`);
    console.log(`  suggestedPromptPrefix: ${profile.suggestedPromptPrefix}`);

    check("Profile: dominantAspectRatio が設定されている", () => {
      if (!profile.dominantAspectRatio) throw new Error("no dominantAspectRatio");
    });

    check("Profile: dominantStyle が設定されている", () => {
      if (!profile.dominantStyle && analyses.length > 0) {
        throw new Error("no dominantStyle");
      }
    });

    check("Profile: dominantColors が配列", () => {
      if (!Array.isArray(profile.dominantColors)) {
        throw new Error("dominantColors is not array");
      }
    });

    // === 4. プロンプト生成 ===
    console.log("\n--- 4. プロンプト生成 ---");

    const scenes = [
      "Scene 1: 主人公が朝の公園を歩くシーン",
      "Scene 2: 雨の中で傘をさすクライマックス",
      "Scene 3: 夕焼けのエンディングシーン",
    ];

    const prompts = pipeline.generatePrompts(profile, scenes);

    for (let i = 0; i < prompts.length; i++) {
      console.log(`  Prompt ${i + 1}: ${prompts[i].slice(0, 80)}...`);
    }

    check("Prompts: シーン数と一致", () => {
      if (prompts.length !== scenes.length) {
        throw new Error(`prompts=${prompts.length}, expected=${scenes.length}`);
      }
    });

    check("Prompts: 各プロンプトにシーン内容が含まれる", () => {
      for (let i = 0; i < scenes.length; i++) {
        if (!prompts[i].includes(scenes[i])) {
          throw new Error("scene not in prompt: " + scenes[i]);
        }
      }
    });

    check("Prompts: スタイルプレフィックスが含まれる", () => {
      if (profile.suggestedPromptPrefix) {
        for (const p of prompts) {
          if (!p.includes(profile.suggestedPromptPrefix)) {
            throw new Error("prefix not in prompt");
          }
        }
      }
    });

    // === 5. フルパイプライン (run) ===
    console.log("\n--- 5. フルパイプライン (run) ---");

    const fullResult = await pipeline.run(tmpDir, scenes);

    check("Run: files が返される", () => {
      if (fullResult.files.length === 0) throw new Error("no files");
    });

    check("Run: analyses が返される", () => {
      if (fullResult.analyses.length === 0 && fullResult.files.length > 0) {
        throw new Error("no analyses");
      }
    });

    check("Run: profile が返される", () => {
      if (!fullResult.profile) throw new Error("no profile");
    });

    check("Run: prompts が返される", () => {
      if (fullResult.prompts.length !== scenes.length) {
        throw new Error("prompts=" + fullResult.prompts.length);
      }
    });

    // === 6. エラーハンドリング ===
    console.log("\n--- 6. エラーハンドリング ---");

    let caught = false;
    try {
      await pipeline.scanDirectory("/nonexistent/path/does/not/exist");
    } catch {
      caught = true;
    }
    check("Error: 存在しないディレクトリで例外", () => {
      if (!caught) throw new Error("no exception thrown");
    });

    const emptyDir = path.join(tmpDir, "empty");
    fs.mkdirSync(emptyDir);
    const emptyFiles = await pipeline.scanDirectory(emptyDir);
    check("Error: 空ディレクトリで空配列", () => {
      if (emptyFiles.length !== 0) throw new Error("not empty");
    });

    // === 7. シンボリックリンクと循環参照 ===
    console.log("\n--- 7. シンボリックリンクと循環参照 ---");

    const linkDir = path.join(tmpDir, "links");
    fs.mkdirSync(linkDir);
    fs.symlinkSync(imgDir, path.join(linkDir, "img-link"));

    const linkFiles = await pipeline.scanDirectory(linkDir);
    check("Symlink: リンク先のファイルを検出", () => {
      if (linkFiles.length === 0) throw new Error("no files from symlink");
    });

    const circularDir = path.join(tmpDir, "circular");
    fs.mkdirSync(circularDir);
    fs.symlinkSync(tmpDir, path.join(circularDir, "loop"));
    fs.writeFileSync(path.join(circularDir, "test.png"), createTestPng(100, 100));

    const circularFiles = await pipeline.scanDirectory(circularDir);
    check("Circular: 循環参照でクラッシュしない", () => {
      const testPng = circularFiles.filter((f) => f.name === "test.png");
      if (testPng.length !== 1) throw new Error("test.png not found");
    });
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }

  // === Summary ===
  console.log("\n" + "=".repeat(50));
  results.forEach((r) => console.log(r));
  console.log("=".repeat(50));
  console.log(`\nTotal: ${passed}/${passed + failed} passed`);

  if (failed > 0) {
    console.error(`\n${failed} 件のテストが失敗しました。`);
    process.exit(1);
  }

  console.log("\nClient Material Pipeline E2E テスト全パス!");
})();
