/**
 * M8 reproducibility probe: one public MediaPipe demo portrait, processed
 * multiple times through the actual Faceface gallery input and real model.
 *
 * This is NOT a diverse-person accuracy study or a calibrated face classifier.
 * Browser-engine/input changes and mild image transforms are recorded, not
 * hidden. The report contains no photographs or facial landmark coordinates.
 *
 * CI needs: a built Vite site, Playwright chromium/webkit and
 * dist/ci-portrait.jpg (the official public MediaPipe example).
 */
import { chromium, webkit, devices } from "playwright";
import { spawn } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { setTimeout as sleep } from "node:timers/promises";

const engine = process.env.FACEFACE_BROWSER ?? "chromium";
if (!["chromium", "webkit"].includes(engine)) throw new Error("Unsupported test engine");
const origin = "http://127.0.0.1:4173";
const server = spawn(process.execPath, ["node_modules/vite/bin/vite.js", "preview",
  "--host", "127.0.0.1", "--port", "4173", "--strictPort"], { stdio: "ignore" });
const sourceIds = [
  "MY25-EYE-01", "MY25-MOUTH-01", "MY25-NOSE-01",
  "MY25-MOUTH-ARC-01", "MY25-EYE-OX-01", "MY25-MOUTH-OX-01",
  "MY25-FACE-ROUND-01", "MY25-NOSE-LONG-01", "MY25-CHIN-WIDE-01",
  "MY25-MOUTH-CATFISH-01"
];
const descriptorIds = [
  "face.aspect", "eyes.openness", "nose.width", "mouth.width",
  "jaw.width", "eyes.spacing", "nose.length", "chin.height",
  "mouth.corner", "mouth.lip"
];

let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 35; attempt++) {
    try {
      if ((await fetch(origin)).ok) { ready = true; break; }
    } catch {}
    await sleep(300);
  }
  if (!ready) throw new Error("Local Vite server failed to start");

  browser = await (engine === "chromium" ? chromium : webkit).launch();
  const page = await browser.newPage({
    ...(engine === "chromium" ? devices["Pixel 7"] : devices["iPhone 13"]),
    viewport: { width: 390, height: 844 }
  });
  const failures = [];
  page.on("pageerror", error => failures.push(error.message));
  await page.goto(origin, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Switch language / 切换语言" }).click();

  // Decode public test fixture in the browser. Canvas generates temporary
  // non-personal image variants; none is checked in or uploaded.
  const variants = await page.evaluate(async () => {
    const image = new Image();
    image.src = "/ci-portrait.jpg";
    await image.decode();
    const results = [];
    // Pixel-wise operations avoid inconsistent CanvasRenderingContext2D.filter
    // support across browser engines. Verify transforms actually changed pixels.
    const settings = [
      { name: "jpeg-recode", brightness: 1, contrast: 1, zoom: 1, scale: 1, quality: .75 },
      { name: "brightness-85", brightness: .85, contrast: 1, zoom: 1, scale: 1, quality: .9 },
      { name: "brightness-115", brightness: 1.15, contrast: 1, zoom: 1, scale: 1, quality: .9 },
      { name: "contrast-90", brightness: 1, contrast: .90, zoom: 1, scale: 1, quality: .9 },
      { name: "center-crop-4pct", brightness: 1, contrast: 1, zoom: 1.04, scale: 1, quality: .9 },
      { name: "resize-75pct", brightness: 1, contrast: 1, zoom: 1, scale: .75, quality: .9 }
    ];
    for (const setting of settings) {
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(image.naturalWidth * setting.scale);
      canvas.height = Math.round(image.naturalHeight * setting.scale);
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Image transform canvas failed");
      const srcWidth = image.naturalWidth / setting.zoom;
      const srcHeight = image.naturalHeight / setting.zoom;
      context.drawImage(image, (image.naturalWidth - srcWidth) / 2,
        (image.naturalHeight - srcHeight) / 2, srcWidth, srcHeight,
        0, 0, canvas.width, canvas.height);
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
      if (setting.brightness !== 1 || setting.contrast !== 1) {
        for (let i = 0; i < pixels.data.length; i += 4) {
          for (let channel = 0; channel < 3; channel++) {
            const value = (pixels.data[i + channel] - 128) * setting.contrast + 128;
            pixels.data[i + channel] = Math.max(0, Math.min(255, value * setting.brightness));
          }
        }
        context.putImageData(pixels, 0, 0);
      }
      // Short-lived aggregate luminance of the test image, no image/landmarks
      // retained in result artifact; confirms real transforms on both engines.
      const values = context.getImageData(0, 0, canvas.width, canvas.height).data;
      let light = 0, count = 0, sampledHash = 0;
      for (let i = 0; i < values.length; i += 4 * 97) {
        const r = values[i], g = values[i + 1], b = values[i + 2];
        light += (r + g + b) / 3;
        sampledHash = (sampledHash * 131 + r * 7 + g * 3 + b) % 1000000007;
        count += 1;
      }
      results.push({
        name: setting.name,
        meanLuminance: Number((light / count).toFixed(2)),
        sampledHash,
        base64: canvas.toDataURL("image/jpeg", setting.quality).split(",")[1]
      });
    }
    return results;
  });
  const byName = new Map(variants.map(v => [v.name, v]));
  const neutral = byName.get("jpeg-recode");
  const darker = byName.get("brightness-85");
  const brighter = byName.get("brightness-115");
  const softer = byName.get("contrast-90");
  if (!(darker.meanLuminance < neutral.meanLuminance - 5 &&
        brighter.meanLuminance > neutral.meanLuminance + 5 &&
        softer.sampledHash !== neutral.sampledHash)) {
    throw new Error("Pixel-level brightness/contrast transformations were not applied");
  }
  const variantLuminance = Object.fromEntries(variants.map(v => [v.name, v.meanLuminance]));

  const officialPortrait = await readFile("dist/ci-portrait.jpg");
  const allVariants = [{ name: "original", bytes: officialPortrait },
    ...variants.map(v => ({ name: v.name, bytes: Buffer.from(v.base64, "base64") }))];

  const snapshots = [];
  for (const variant of allVariants) {
    await page.locator('input[type="file"]').setInputFiles({
      name: variant.name + ".jpg", mimeType: "image/jpeg", buffer: variant.bytes
    });
    await page.waitForFunction(() =>
      document.querySelector(".report") !== null ||
      (document.querySelector(".error-message") !== null &&
       document.querySelector(".processing-layer") === null),
      null, { timeout: 90000 });
    if (!(await page.locator(".report").count())) {
      throw new Error(variant.name + ": no report. " +
        await page.locator(".error-message").allTextContents());
    }
    // Product now defaults to quick life reading: source metrics are opt-in.
    const detailed=page.getByRole("button",{name:"详细版"});
    if (await page.locator(".observations").count()!==0 ||
        await page.locator(".source-detail").count()!==0 ||
        await page.locator(".life-reading-brief").count()!==1) {
      throw new Error("M8 stability test: brief mode unexpectedly exposed detailed source data");
    }
    await detailed.click();
    await page.getByRole("button", { name: "查看计算依据" }).click();
    const snapshot = await page.evaluate(({ descriptorIds, sourceIds }) => {
      const observations = Array.from(document.querySelectorAll(".observation"));
      const cards = Array.from(document.querySelectorAll(".source-detail"));
      if (observations.length !== descriptorIds.length ||
          cards.length !== sourceIds.length) {
        throw new Error("Unexpected feature or historical card count");
      }
      const ratios = {};
      const categories = {};
      observations.forEach((node, i) => {
        const measure = node.querySelector("small")?.textContent ?? "";
        const ratio = /:\s*([0-9]+(?:\.[0-9]+)?)/.exec(measure);
        if (!ratio) throw new Error("Unable to read measured ratio: " + measure);
        ratios[descriptorIds[i]] = Number(ratio[1]);
        categories[descriptorIds[i]] = node.querySelector("strong")?.textContent ?? "";
      });
      const related = cards.flatMap((node, i) =>
        (node.querySelector("h4 span")?.textContent ?? "").includes("相关观察")
          ? [sourceIds[i]] : []);
      return { ratios, categories, related };
    }, { descriptorIds, sourceIds });
    snapshots.push({ variant: variant.name, ...snapshot });
    await page.getByRole("button", { name: "清除画面 / 重新拍摄" }).click();
    await page.locator('input[type="file"]').waitFor();
  }

  const original = snapshots[0];
  const comparisons = snapshots.slice(1).map(snapshot => {
    const ratioDeltas = Object.fromEntries(descriptorIds.map(id =>
      [id, Number(Math.abs(snapshot.ratios[id] - original.ratios[id]).toFixed(3))]));
    const categoryChanges = descriptorIds.filter(id =>
      original.categories[id] !== snapshot.categories[id]);
    const relatedGained = snapshot.related.filter(id => !original.related.includes(id));
    const relatedLost = original.related.filter(id => !snapshot.related.includes(id));
    return {
      variant: snapshot.variant,
      ratioDeltas,
      categoryChanges,
      relatedGained,
      relatedLost,
      unsupported: []
    };
  });

  const summary = {
    fixture: "Google MediaPipe public sample portrait.jpg",
    engine,
    scope: "One-photo mild-transform reproducibility ONLY; no cross-person accuracy claims",
    descriptorIds,
    sourceIds,
    original: { ratios: original.ratios, related: original.related },
    variantLuminance,
    comparisons,
    scriptErrors: failures
  };
  await writeFile("m8-stability-" + engine + ".json", JSON.stringify(summary, null, 2) + "\n");
  console.log("M8_STABILITY_SUMMARY " + JSON.stringify(summary));
  if (failures.length) throw new Error("Browser script errors: " + failures.join(" | "));
  if (comparisons.some(c => Object.values(c.ratioDeltas).some(x => !Number.isFinite(x)))) {
    throw new Error("Non-finite or unparseable model measurement during robustness test");
  }
  // This gate tests one pinned public image and specifically these mild
  // transforms, not arbitrary people or extreme pose changes.
  const changed = comparisons.filter(c =>
    c.categoryChanges.length || c.relatedGained.length || c.relatedLost.length);
  if (changed.length) {
    throw new Error("M8 public-image regression: category/source flips detected " +
      JSON.stringify(changed.map(c => ({
        variant: c.variant, categories: c.categoryChanges,
        relatedGained: c.relatedGained, relatedLost: c.relatedLost
      }))));
  }
  console.log("PASS M8: " + (snapshots.length) + " runs of one public portrait, " +
    engine + "; category flips and classical-link changes recorded for review");
} finally {
  await browser?.close();
  server.kill();
}
