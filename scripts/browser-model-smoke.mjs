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
  const unexpectedExternalRequests = [];
  page.on("pageerror", error => scriptErrors.push(error.message));
  page.on("request", request => {
    if (!/^https?:/.test(request.url())) return;
    const uri = new URL(request.url());
    if (!["GET", "HEAD"].includes(request.method())) {
      unexpectedNetworkWrites.push(request.method() + " " + uri.origin + uri.pathname);
    }
    // Product code should only load its own static UI and pinned
    // jsDelivr WASM + Google model. Any newly added external GET
    // endpoint must be reviewed; GET can also exfiltrate query data.
    const onOwnSite = uri.origin === origin;
    const pinnedWasm = uri.host === "cdn.jsdelivr.net" &&
      uri.pathname.startsWith("/npm/@mediapipe/tasks-vision@1.2.3/wasm/");
    const pinnedModel = uri.host === "storage.googleapis.com" &&
      uri.pathname === "/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";
    if (!(onOwnSite || pinnedWasm || pinnedModel) || uri.search) {
      unexpectedExternalRequests.push(uri.origin + uri.pathname + (uri.search ? " [query present]" : ""));
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
        // Move the virtual camera closer to the public demo face. The
        // original fixture is correctly classified TOO SMALL by the live
        // guide; a real person would step toward their webcam instead.
        const zoom = 1.95;
        const srcWidth = image.naturalWidth / zoom;
        const srcHeight = image.naturalHeight / zoom;
        const paint = () => {
          context.fillStyle = "#202b29";
          context.fillRect(0, 0, canvas.width, canvas.height);
          // Deliberate temporary absence of a face tests green -> red reset.
          if (!window.__facefaceTestBlank) {
            context.drawImage(image,
              (image.naturalWidth - srcWidth) / 2,
              0, // face is high in the original public full-body portrait
              srcWidth, srcHeight, 0, 0, canvas.width, canvas.height);
          }
        };
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
    // M10: the shutter is intentionally manual. A red outline must NOT
    // permit capture. After 3 continuous seconds of real model alignment,
    // the SVG turns green, but the page must not capture by itself.
    const shutter=page.getByRole("button", { name: "拍摄并本地分析" });
    if (await shutter.isEnabled()) {
      throw new Error("M10 shutter should not be available before 3s positioning");
    }
    if (await page.locator(".live-face-svg").count() !== 1 ||
        await page.locator(".guide-oval").count() !== 0) {
      throw new Error("M11 live SVG contour has not replaced the fixed camera guide");
    }
    await page.waitForFunction(() => {
      const svg = document.querySelector(".live-face-svg");
      const path = svg?.querySelector(".live-face-outline");
      const progress = Number(svg?.getAttribute("data-progress") || 0);
      return path?.getAttribute("d")?.includes(" C ") &&
        progress > 0 && progress < 1 &&
        !!svg?.querySelector(".live-face-progress");
    }, null, { timeout: 20000 });
    console.log("M11: green contour is visibly tracing the true face clockwise; no shutter triggered");
    try {
      await page.waitForFunction(() =>
        document.querySelector(".guide-status")?.getAttribute("data-guide-status") === "ready",
        null, { timeout: 14000 });
    } catch (cause) {
      const diagnostic = await page.evaluate(() => ({
        guide: document.querySelector(".guide-status")?.getAttribute("data-guide-status"),
        reason: document.querySelector(".guide-status")?.getAttribute("data-guide-reason"),
        hint: document.querySelector(".guide-status")?.textContent,
        error: document.querySelector(".error-message")?.textContent,
        videoSize: (() => { const v=document.querySelector("video");return v ? [v.videoWidth,v.videoHeight,v.readyState,v.currentTime] : null; })(),
        stage: (()=>{const r=document.querySelector(".camera-stage")?.getBoundingClientRect();return r?[r.width,r.height]:null;})(),
        svg: (()=>{const r=document.querySelector(".face-guide-svg")?.getBoundingClientRect();return r?[r.width,r.height]:null;})()
      }));
      throw new Error("M10 alignment not ready: " + JSON.stringify(diagnostic) + " " + String(cause));
    }
    if (await page.locator(".live-face-svg--ready").count() !== 1 ||
        !(await shutter.isEnabled())) {
      throw new Error("M11 manual shutter did not unlock after green face outline");
    }
    if (await page.locator(".report").count()) {
      throw new Error("M11 triggered an automatic photo without explicit consent");
    }
    // Side SVG is a deliberate preview, not a supported face-reading mode.
    await page.getByRole("button", { name: "侧脸轮廓（预览）" }).click();
    if (await shutter.isEnabled() ||
        await page.locator('.face-guide-svg[data-guide-mode="side"]').count() !== 1) {
      throw new Error("M10 side-profile preview incorrectly enabled front-face capture");
    }
    await page.getByRole("button", { name: "正脸" }).click();
    await page.waitForFunction(() =>
      document.querySelector(".guide-status")?.getAttribute("data-guide-status") === "ready",
      null, { timeout: 14000 });
    // Losing the face must return the guide to red and lock the manual shutter.
    await page.evaluate(() => { window.__facefaceTestBlank = true; });
    await page.waitForFunction(() =>
      document.querySelector(".guide-status")?.getAttribute("data-guide-status") === "no-face",
      null, { timeout: 8000 });
    if (await shutter.isEnabled() ||
        await page.locator(".live-face-svg--ready").count() !== 0 ||
        await page.locator(".live-face-progress").count() !== 0) {
      throw new Error("M11 face loss did not immediately clear the green contour");
    }
    await page.evaluate(() => { window.__facefaceTestBlank = false; });
    await page.waitForFunction(() =>
      document.querySelector(".guide-status")?.getAttribute("data-guide-status") === "ready",
      null, { timeout: 14000 });
    if (await page.locator(".report").count()) {
      throw new Error("M10 auto-captured instead of waiting for manual shutter");
    }
    await shutter.click();
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
    briefInsightCount: document.querySelectorAll(".reading-insights p").length,
    detailedCollapsed: !document.querySelector("details.source-details")?.open,
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
  if (diagnostics.descriptionCount !== 10 ||
      diagnostics.historicalHighlights < 1 || diagnostics.historicalHighlights > 2 ||
      diagnostics.briefInsightCount < 1 || !diagnostics.detailedCollapsed ||
      diagnostics.historicalCards !== 9 || diagnostics.historicalFrameworks !== 2 ||
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
      !savedText.includes("【详细版：全部面部形态观察") ||
      !savedText.includes("或細長") ||
      !savedText.includes("口須方大") ||
      !savedText.includes("梁柱端直") ||
      !savedText.includes("仰月口") ||
      !savedText.includes("牛眼") ||
      !savedText.includes("牛口") ||
      !savedText.includes("面圓光澤") ||
      !savedText.includes("鼻長有壽") ||
      !savedText.includes("頦為地") ||
      !savedText.includes("古籍文化解读（非现实预测）") ||
      !savedText.includes("【古籍取象背景") ||
      !savedText.includes("PDF 零起页86") ||
      !savedText.includes("扫描 PDF 零起页87") ||
      !savedText.includes("扫描 PDF 零起页52") ||
      !savedText.includes("扫描 PDF 零起页77") ||
      !savedText.includes("扫描 PDF 零起页34") ||
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
  if (englishObservations.length !== 10 ||
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
      !englishReport.includes("DETAILED OBSERVATIONS") ||
      !englishReport.includes("Original wording: 或細長") ||
      !englishReport.includes("not a certified translation") ||
      !englishReport.includes("PDF zero-based page 27") ||
      !englishReport.includes("仰月口") ||
      !englishReport.includes("Four Rivers") ||
      !englishReport.includes("PDF zero-based page 86") ||
      !englishReport.includes("PDF zero-based page 87") ||
      !englishReport.includes("PDF zero-based page 52") ||
      !englishReport.includes("PDF zero-based page 77") ||
      !englishReport.includes("PDF zero-based page 34") ||
      !englishReport.includes("What the historic text says")) {
    throw new Error("English report export missing original phrases or source caveats");
  }
  // M9: a willing participant can re-analyze another local photo and inspect
  // changes without sending either photo or landmark coordinates to a server.
  // The emulated camera now *reframes* the public portrait to align its face.
  // For an exact same-image comparison we must upload that CAPTURED frame,
  // not the different, uncropped original file. WebKit already used the
  // original photo both times. No CI image is persisted after the test.
  const secondPhoto = engine === "chromium"
    ? {
        name: "same-captured-frame.png",
        mimeType: "image/png",
        buffer: Buffer.from(await page.locator("canvas.photo-canvas").evaluate(el =>
          el.toDataURL("image/png").split(",")[1]), "base64")
      }
    : "dist/ci-portrait.jpg";
  await page.locator('input[aria-label="Choose a second photo of the same person"]')
    .setInputFiles(secondPhoto);
  await page.waitForSelector(".consistency-panel", { timeout: 90000 });
  const comparisonStats = await page.locator(".consistency-totals strong").allTextContents();
  if (comparisonStats.join("|") !== "0 / 10|0 / 9") {
    throw new Error("M9 identical-picture local comparison drifted: " + comparisonStats.join("|"));
  }
  await page.locator(".consistency-details summary").click();
  if ((await page.locator(".consistency-item").count()) !== 10 ||
      (await page.locator(".consistency-source-change").count()) !== 0) {
    throw new Error("M9 local comparison did not explain all ten descriptors");
  }
  // The local comparison is session memory only and must be gone on reset.
  await page.getByRole("button", { name: "Clear photo / Take another" }).click();
  if (await page.locator(".consistency-panel").count()) {
    throw new Error("M9 local comparison data persisted after clearing the photo");
  }
  if (unexpectedNetworkWrites.length || unexpectedExternalRequests.length) {
    throw new Error("Unexpected network activity after M9 local comparison: " +
      JSON.stringify({ unexpectedNetworkWrites, unexpectedExternalRequests }));
  }
  const additionalStorage = await page.evaluate(async () => ({
    cookies: document.cookie,
    localKeys: Object.keys(localStorage),
    sessionKeys: Object.keys(sessionStorage),
    databases: typeof indexedDB.databases === "function"
      ? (await indexedDB.databases()).map(d => d.name) : [],
    caches: typeof caches !== "undefined" ? await caches.keys() : []
  }));
  if (additionalStorage.cookies || additionalStorage.localKeys.length ||
      additionalStorage.sessionKeys.length || additionalStorage.databases.length ||
      additionalStorage.caches.length) {
    throw new Error("M9 unexpected app persistence: " + JSON.stringify(additionalStorage));
  }
  console.log("M9 PASS (" + engine + "): two local photo analyses, zero categorical/source drift, no unapproved outbound requests, no persistent app storage");
  await page.getByRole("link", { name: "Privacy notice / 隐私说明" }).click();
  await page.getByRole("heading", { name: "Privacy notice / 隐私说明" }).waitFor({ timeout: 10000 });
  console.log("PASS (" + engine + "): " + (engine === "webkit" ? "local file" : "camera fixture") + " -> real MediaPipe -> source report -> local download, privacy page, no network writes/storage.");
} finally {
  if (browser) await browser.close();
  preview.kill();
}
