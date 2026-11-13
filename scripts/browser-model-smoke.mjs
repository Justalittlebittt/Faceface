/**
 * CI-only integration smoke. Uses Google's public MediaPipe example portrait.
 * The portrait is downloaded temporarily in CI; no user images are required,
 * and no image, landmarks, or per-person report are uploaded by this script.
 *
 * Requires: npm install --no-save playwright@1.65.0
 *           npx playwright install --with-deps chromium
 *           npm run build
 *           curl official portrait to dist/ci-portrait.jpg
 */
import { chromium, webkit, devices } from "playwright";
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { setTimeout as sleep } from "node:timers/promises";

const origin = "http://127.0.0.1:4173";
const engine = process.env.FACEFACE_BROWSER ?? "chromium";
if (!["chromium", "webkit"].includes(engine)) throw new Error("Unrecognized browser test engine");
const preview = spawn(process.execPath, ["node_modules/vite/bin/vite.js", "preview",
  "--host", "127.0.0.1", "--port", "4173", "--strictPort"], { stdio: "ignore" });

let browser;
try {
  let online = false;
  for (let attempt = 0; attempt < 30; attempt++) {
    try {
      const response = await fetch(origin);
      if (response.ok) { online = true; break; }
    } catch { /* local server not ready yet */ }
    await sleep(300);
  }
  if (!online) throw new Error("Vite preview did not start");

  browser = await (engine === "webkit" ? webkit : chromium).launch({ headless: true });
  const mobileProfile = engine === "webkit" ? devices["iPhone 13"] : devices["Pixel 7"];
  const page = await browser.newPage({ ...mobileProfile, viewport: { width: 390, height: 844 } });
  console.log("Mobile-engine integration test:", engine);
  const scriptErrors = [];
  const remoteFailures = [];
  const unexpectedNetworkWrites = [];
  page.on("pageerror", error => scriptErrors.push(error.message));
  page.on("request", request => {
    if (!["GET", "HEAD"].includes(request.method()) && /^https?:/.test(request.url())) {
      unexpectedNetworkWrites.push(request.method() + " " + request.url());
    }
  });
  page.on("requestfailed", request => {
    if (request.url().includes("jsdelivr") || request.url().includes("googleapis")) {
      remoteFailures.push(request.url() + ": " + request.failure()?.errorText);
    }
  });
  if (engine === "chromium") {
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      configurable: true,
      value: async () => {
        const image = new Image();
        image.src = "/ci-portrait.jpg";
        await image.decode();
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Camera fixture canvas unavailable");
        const paint = () => context.drawImage(image, 0, 0);
        paint();
        const stream = canvas.captureStream(15);
        // Keep frame delivery alive while video waits to start.
        const ticker = setInterval(paint, 100);
        stream.getTracks()[0]?.addEventListener("ended", () => clearInterval(ticker), { once: true });
        return stream;
      }
    });
  });

  }

  await page.goto(origin, { waitUntil: "domcontentloaded", timeout: 30000 });
  const robots = await page.locator('meta[name="robots"]').getAttribute("content");
  if (!robots?.includes("noindex")) throw new Error("Preview must remain noindex");
  // The actual international preview defaults to English, without persistent storage.
  const initialHeading = await page.locator(".hero h1").textContent();
  if (!initialHeading?.includes("Read facial features")) throw new Error("English must be default");
  await page.getByRole("button", { name: "Switch language / 切换语言" }).click();
  const localHeading = await page.locator(".hero h1").textContent();
  if (!localHeading?.includes("让面部形态")) throw new Error("Chinese UI toggle failed");
  if (engine === "webkit") {
    // WebKit's headless CanvasCaptureStream fixture may not deliver frames.
    // This tests the real model on the actual picture via our optional local-file
    // path, while Chromium still tests the camera/video flow above.
    await page.locator('input[aria-label="从本地选择照片"]').setInputFiles("dist/ci-portrait.jpg");
  } else {
    await page.getByRole("button", { name: "开启前置摄像头" }).click();
    await page.getByRole("button", { name: "拍摄并本地分析" }).waitFor({ timeout: 15000 });
    await page.waitForFunction(() => {
      const video = document.querySelector("video");
      return video instanceof HTMLVideoElement && video.readyState >= 2 && video.videoWidth > 0;
    }, { timeout: 15000 });
    await page.getByRole("button", { name: "拍摄并本地分析" }).click();
  }

  await page.waitForFunction(() => {
    return document.querySelector(".report") !== null ||
      (document.querySelector(".error-message") !== null &&
       document.querySelector(".processing-layer") === null);
  }, { timeout: 90000 });

  // Use the existing user-facing measurement toggle; do not export face coordinates.
  await page.getByRole("button", { name: "查看计算依据" }).click();
  const measuredRatios = await page.locator(".observation small").allTextContents();
  const previewTransform = await page.locator("canvas.photo-canvas").evaluate(el =>
    getComputedStyle(el).transform
  );
  const isMirrored = previewTransform !== "none" && previewTransform.startsWith("matrix(-1");
  if (isMirrored !== (engine === "chromium")) {
    throw new Error("Wrong photo preview orientation for " + engine + ": " + previewTransform);
  }
  console.log("Geometry metrics (" + engine + "):", JSON.stringify(measuredRatios));
  // The pinned public portrait previously yielded eye ratios .221 (Chromium)
  // and .219 (WebKit), straddling the old .220 cutoff with contradictory labels.
  // Both should now be described as borderline, not opposite face shapes.
  const eyeLabel = await page.locator(".observation").nth(1).locator("strong").textContent();
  if (!eyeLabel?.includes("接近实验分类边界")) {
    throw new Error(engine + " still assigns a brittle eye shape label: " + eyeLabel);
  }


  const diagnostics = await page.evaluate(() => ({
    report: document.querySelector(".report")?.textContent || null,
    cameraError: document.querySelector(".workbench .error-message")?.textContent || null,
    descriptionCount: document.querySelectorAll(".observation").length,
    historicalHighlights: document.querySelectorAll(".source-highlight").length,
    historicalCards: document.querySelectorAll(".source-detail").length,
    historicalFrameworks: document.querySelectorAll(".framework-note").length,
    sourceLabels: [...document.querySelectorAll(".source-detail h4")].map(node => node.textContent),
    detailedReport: document.querySelector(".source-details")?.textContent || null,
    modelTiming: document.querySelector(".report [role=status]")?.textContent || null
  }));
  console.log("Integration result (public Google sample only):", JSON.stringify({
    ...diagnostics,
    report: diagnostics.report?.slice(0, 900)
  }));
  if (remoteFailures.length) console.log("Model/CDN failures:", remoteFailures.join(" | "));
  if (scriptErrors.length) console.log("Browser JS errors:", scriptErrors.join(" | "));
  if (diagnostics.descriptionCount !== 9 ||
      diagnostics.historicalHighlights < 1 || diagnostics.historicalHighlights > 2 ||
      diagnostics.historicalCards !== 4 || diagnostics.historicalFrameworks !== 2 ||
      !diagnostics.detailedReport?.includes("不据此作出相型判断") ||
      diagnostics.cameraError || scriptErrors.length) {
    throw new Error("Real browser face-to-source-linked report integration failed");
  }
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 15000 }),
    page.getByRole("button", { name: "保存或分享文化报告" }).click()
  ]);
  const downloadedPath = await download.path();
  if (!downloadedPath) throw new Error("No downloadable report file");
  const savedText = await readFile(downloadedPath, "utf8");
  if (!savedText.includes("【简洁报告】") ||
      !savedText.includes("或細長") ||
      !savedText.includes("口須方大") ||
      !savedText.includes("梁柱端直") ||
      !savedText.includes("仰月口") ||
      !savedText.includes("【古籍取象背景") ||
      !savedText.includes("PDF 零起页86") ||
      !savedText.includes("扫描 PDF 零起页27")) {
    throw new Error("Local report export is missing observed content or source provenance");
  }
  if (unexpectedNetworkWrites.length) {
    throw new Error("Non-GET network requests detected: " + unexpectedNetworkWrites.join(" | "));
  }
  const persistence = await page.evaluate(() => ({
    localKeys: Object.keys(localStorage),
    sessionKeys: Object.keys(sessionStorage)
  }));
  if (persistence.localKeys.length || persistence.sessionKeys.length) {
    throw new Error("Unexpected persisted browser storage keys: " + JSON.stringify(persistence));
  }
  await page.getByRole("button", { name: "Switch language / 切换语言" }).click();
  const englishObservations = await page.locator(".observation strong").allTextContents();
  if (englishObservations.length !== 9 ||
      englishObservations.some(x => !/[A-Za-z]/.test(x))) {
    throw new Error("English measurements not rendered after language switch");
  }
  if (!(await page.locator(".cultural-reading").textContent())?.includes("Source:")) {
    throw new Error("English cultural references were not displayed");
  }
  const [englishDownload] = await Promise.all([
    page.waitForEvent("download", { timeout: 15000 }),
    page.getByRole("button", { name: "Save or share the report" }).click()
  ]);
  const englishPath = await englishDownload.path();
  if (!englishPath) throw new Error("Missing English downloaded file");
  const englishReport = await readFile(englishPath, "utf8");
  if (!englishReport.includes("SHORT REPORT") ||
      !englishReport.includes("Original wording: 或細長") ||
      !englishReport.includes("not a certified translation") ||
      !englishReport.includes("PDF zero-based page 27") ||
      !englishReport.includes("仰月口") ||
      !englishReport.includes("Four Rivers") ||
      !englishReport.includes("PDF zero-based page 86")) {
    throw new Error("English report export missing original phrases or source caveats");
  }
  await page.getByRole("link", { name: "Privacy notice / 隐私说明" }).click();
  await page.getByRole("heading", { name: "Privacy notice / 隐私说明" }).waitFor({ timeout: 10000 });
  console.log("PASS (" + engine + "): " + (engine === "webkit" ? "local file" : "camera fixture") + " -> real MediaPipe -> source report -> local download, privacy page, no network writes/storage.");
} finally {
  if (browser) await browser.close();
  preview.kill();
}
