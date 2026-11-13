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

  await page.goto(origin, { waitUntil: "domcontentloaded", timeout: 30000 });
  const robots = await page.locator('meta[name="robots"]').getAttribute("content");
  if (!robots?.includes("noindex")) throw new Error("Preview must remain noindex");
  await page.getByRole("button", { name: "开启前置摄像头" }).click();
  await page.getByRole("button", { name: "拍摄并本地分析" }).waitFor({ timeout: 15000 });
  await page.waitForFunction(() => {
    const video = document.querySelector("video");
    return video instanceof HTMLVideoElement && video.readyState >= 2 && video.videoWidth > 0;
  }, { timeout: 15000 });
  await page.getByRole("button", { name: "拍摄并本地分析" }).click();

  await page.waitForFunction(() => {
    return document.querySelector(".report") !== null ||
      (document.querySelector(".error-message") !== null &&
       document.querySelector(".processing-layer") === null);
  }, { timeout: 90000 });

  const diagnostics = await page.evaluate(() => ({
    report: document.querySelector(".report")?.textContent || null,
    cameraError: document.querySelector(".workbench .error-message")?.textContent || null,
    descriptionCount: document.querySelectorAll(".observation").length,
    historicalHighlights: document.querySelectorAll(".source-highlight").length,
    historicalCards: document.querySelectorAll(".source-detail").length,
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
  if (diagnostics.descriptionCount !== 5 || diagnostics.historicalHighlights !== 2 ||
      diagnostics.historicalCards !== 3 ||
      !diagnostics.detailedReport?.includes("不能用其他比例替代原文条件") ||
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
  await page.getByRole("link", { name: "隐私说明 / Privacy notice" }).click();
  await page.getByRole("heading", { name: "Privacy notice / 隐私说明" }).waitFor({ timeout: 10000 });
  console.log("PASS (" + engine + "): camera fixture -> real MediaPipe -> source report -> local download, privacy page, no network writes/storage.");
} finally {
  if (browser) await browser.close();
  preview.kill();
}
