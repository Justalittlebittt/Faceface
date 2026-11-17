/**
 * Faceface camera guidance. The visible outline is an anatomical SVG hint,
 * not a biometric identity boundary. Only an actual MediaPipe face with a
 * mostly-inside facial perimeter can start the three-second readiness countdown. Capture is always manual.
 *
 * Calculations are pure and account for mirrored front-camera video and
 * object-fit:contain letterboxing. No image or landmark data is persisted.
 */
import { describeLandmarks, type Point } from "./descriptors.ts";

export const READY_HOLD_MS = 3000;
export const MAX_SAMPLE_GAP_MS = 1100;
export const GUIDE_VIEW = { width: 300, height: 420 } as const;

export type GuideMode = "front" | "side";
export type GuideState =
  "loading" | "no-face" | "multiple" | "pose" | "too-small" |
  "too-large" | "outside" | "aligned" | "side-preview";

export type Rect = { x: number; y: number; width: number; height: number };
export type GuideCheck = { state: GuideState; coverage: number; reason?: string };
export type Hold = { startedAt: number | null; lastSeenAt: number | null; progress: number; complete: boolean };

export const EMPTY_HOLD: Hold = { startedAt: null, lastSeenAt: null, progress: 0, complete: false };

// Smooth-front-SVG approximate interior. Polygon samples follow the same
// crown -> temples -> cheeks -> jaw -> chin path as the rendered outline.
// Ears are intentionally not part of the required facial perimeter.
const leftContour: readonly [number, number][] = [
  [150, 46], [120, 47], [95, 55], [75, 70], [60, 95],
  [50, 120], [47, 146], [45, 177], [48, 207],
  [56, 236], [70, 267], [87, 298], [105, 325],
  [128, 350], [150, 363]
];
const silhouette: readonly [number, number][] = [
  ...leftContour,
  ...leftContour.slice(1, -1).reverse().map(([x, y]) => [300 - x, y] as [number, number])
];

function insideOutline(x: number, y: number): boolean {
  let inside = false;
  for (let i = 0, j = silhouette.length - 1; i < silhouette.length; j = i++) {
    const [xi, yi] = silhouette[i];
    const [xj, yj] = silhouette[j];
    if ((yi > y) !== (yj > y) &&
        x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

// Ordered MediaPipe FaceMesh perimeter, excluding ears and hair beyond the
// model face contour. Percentage of these points inside SVG is the actual gate.
export const FACE_OVAL_INDICES = [
  10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
  397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
  172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
] as const;

export function checkFrontGuide(
  faces: readonly (readonly Point[])[],
  image: { width: number; height: number },
  stage: Rect,
  guide: Rect,
  mirrored = true
): GuideCheck {
  if (!faces.length) return { state: "no-face", coverage: 0 };
  if (faces.length !== 1) return { state: "multiple", coverage: 0 };
  if (image.width <= 0 || image.height <= 0 || stage.width <= 0 || stage.height <= 0 ||
      guide.width <= 0 || guide.height <= 0) return { state: "outside", coverage: 0 };
  // The analysis classifier already rejects heavily rolled/yawed, clipped,
  // multi-person or incomplete front-facing landmarks.
  const validity = describeLandmarks(faces, image);
  if (validity.status !== "ok") {
    return { state: "pose", coverage: 0, reason: validity.message };
  }
  const face = faces[0];
  if (FACE_OVAL_INDICES.some(index => !face[index] ||
      !Number.isFinite(face[index].x) || !Number.isFinite(face[index].y))) {
    return { state: "pose", coverage: 0 };
  }

  // Stage and video have the same box. Browser CSS uses object-fit:contain,
  // so portrait cameras on landscape PCs can have letterboxing.
  const ratio = image.width / image.height;
  const drawWidth = Math.min(stage.width, stage.height * ratio);
  const drawHeight = drawWidth / ratio;
  const xPad = (stage.width - drawWidth) / 2;
  const yPad = (stage.height - drawHeight) / 2;
  const mapped = FACE_OVAL_INDICES.map(index => {
    const point = face[index];
    const displayedX = xPad + (mirrored ? 1 - point.x : point.x) * drawWidth;
    const displayedY = yPad + point.y * drawHeight;
    return {
      x: (displayedX - (guide.x - stage.x)) * GUIDE_VIEW.width / guide.width,
      y: (displayedY - (guide.y - stage.y)) * GUIDE_VIEW.height / guide.height
    };
  });
  const xs = mapped.map(p => p.x);
  const ys = mapped.map(p => p.y);
  const faceWidth = Math.max(...xs) - Math.min(...xs);
  const faceHeight = Math.max(...ys) - Math.min(...ys);
  const debugSize = "guide-relative width " + Math.round(faceWidth) +
    ", height " + Math.round(faceHeight) +
    ", center " + Math.round((Math.max(...xs) + Math.min(...xs)) / 2) +
    "/" + Math.round((Math.max(...ys) + Math.min(...ys)) / 2);
  if (faceWidth < 115 || faceHeight < 215) return { state: "too-small", coverage: 0, reason: debugSize };
  if (faceWidth > 224 || faceHeight > 366) return { state: "too-large", coverage: 0, reason: debugSize };

  const coverage = mapped.filter(point => insideOutline(point.x, point.y)).length / mapped.length;
  const centerX = (Math.max(...xs) + Math.min(...xs)) / 2;
  const centerY = (Math.max(...ys) + Math.min(...ys)) / 2;
  // >=85% of the perimeter fits the actual silhouette; geometric center
  // must also be near the guide middle. No false confidence for a tiny face.
  if (coverage < 0.85 || Math.abs(centerX - 150) > 32 ||
      Math.abs(centerY - 207) > 46) return {
        state: "outside", coverage,
        reason: "coverage " + Math.round(coverage * 100) +
          "%, center " + Math.round(centerX) + "/" + Math.round(centerY) +
          ", " + debugSize
      };
  return { state: "aligned", coverage };
}

export function advanceHold(state: Hold, now: number, aligned: boolean): Hold {
  if (!aligned || !Number.isFinite(now)) return EMPTY_HOLD;
  if (state.startedAt === null || state.lastSeenAt === null ||
      now < state.lastSeenAt || now - state.lastSeenAt > MAX_SAMPLE_GAP_MS) {
    return { startedAt: now, lastSeenAt: now, progress: 0, complete: false };
  }
  const progress = Math.min(1, Math.max(0, (now - state.startedAt) / READY_HOLD_MS));
  return { startedAt: state.startedAt, lastSeenAt: now, progress, complete: progress >= 1 };
}
