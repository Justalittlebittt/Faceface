/**
 * Camera-only, on-device face-contour progress.
 * No fixed facial template: the SVG traces the current MediaPipe face oval.
 * Valid near-front pose + adequate framing + stationary hold for 3 seconds
 * unlocks a MANUAL shutter, never automatic photography.
 */
import { describeLandmarks, type Point } from "./descriptors.ts";

export const READY_HOLD_MS = 3000;
export const MAX_SAMPLE_GAP_MS = 1100;
export type GuideMode = "front" | "side";
export type GuideState = "loading" | "no-face" | "multiple" | "pose" |
  "too-small" | "too-large" | "outside" | "moving" | "aligned" | "side-preview";

export type Rect = { x: number; y: number; width: number; height: number };
export type XY = { x: number; y: number };
export type FaceAnchor = { cx: number; cy: number; width: number; height: number };
export type FaceGuideFrame = { state: GuideState; points: XY[]; anchor: FaceAnchor | null };
export type Hold = { startedAt: number | null; lastSeenAt: number | null; progress: number; complete: boolean };
export type TrackingResult = { hold: Hold; anchor: FaceAnchor | null; moved: boolean };

export const EMPTY_HOLD: Hold = { startedAt: null, lastSeenAt: null, progress: 0, complete: false };

// MediaPipe oval begins at forehead index 10 and wraps the cheeks and chin.
// Mirrored cameras reverse winding; clockwisePath() restores screen-clockwise
// order while keeping the top-of-forehead starting point unchanged.
export const FACE_OVAL_INDICES = [
  10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
  397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
  172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
] as const;

export function projectFaceGuide(
  faces: readonly (readonly Point[])[],
  image: { width: number; height: number },
  stage: Rect,
  mirrored = true
): FaceGuideFrame {
  const blank = (state: GuideState): FaceGuideFrame => ({ state, points: [], anchor: null });
  if (!faces.length) return blank("no-face");
  if (faces.length !== 1) return blank("multiple");
  if (image.width <= 0 || image.height <= 0 || stage.width <= 0 || stage.height <= 0) {
    return blank("outside");
  }
  const face = faces[0];
  if (FACE_OVAL_INDICES.some(i => !face[i] ||
      !Number.isFinite(face[i].x) || !Number.isFinite(face[i].y))) {
    return blank("pose");
  }

  // CSS object-fit: contain, centered inside camera stage, followed by the
  // front-camera horizontal mirror. Works for PC letterboxing and phones.
  const scale = Math.min(stage.width / image.width, stage.height / image.height);
  const drawWidth = image.width * scale;
  const drawHeight = image.height * scale;
  const xPad = (stage.width - drawWidth) / 2;
  const yPad = (stage.height - drawHeight) / 2;
  const points = FACE_OVAL_INDICES.map(index => {
    const p = face[index];
    return {
      x: xPad + (mirrored ? 1 - p.x : p.x) * drawWidth,
      y: yPad + p.y * drawHeight
    };
  });
  const xs = points.map(p => p.x), ys = points.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const faceWidth = maxX - minX, faceHeight = maxY - minY;
  const anchor: FaceAnchor = {
    cx: ((minX + maxX) / 2 - xPad) / drawWidth,
    cy: ((minY + maxY) / 2 - yPad) / drawHeight,
    width: faceWidth / drawWidth,
    height: faceHeight / drawHeight
  };
  const result = (state: GuideState): FaceGuideFrame => ({ state, points, anchor });
  // These are broad camera framing checks, not anthropometric thresholds.
  if (faceWidth < drawWidth * .23 || faceHeight < drawHeight * .28) {
    return result("too-small");
  }
  if (faceWidth > drawWidth * .87 || faceHeight > drawHeight * .88) {
    return result("too-large");
  }
  const edge = Math.min(drawWidth, drawHeight) * .012;
  if (minX < xPad + edge || maxX > xPad + drawWidth - edge ||
      minY < yPad + edge || maxY > yPad + drawHeight - edge) {
    return result("outside");
  }
  // A pretty outline is not proof of good pose: reuse the same near-front
  // quality assessment as the report, so a side face cannot become ready.
  return result(describeLandmarks(faces, image).status === "ok" ? "aligned" : "pose");
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

export function advanceStationaryHold(
  previous: Hold, origin: FaceAnchor | null,
  current: FaceAnchor | null, now: number, acceptable: boolean
): TrackingResult {
  if (!acceptable || !current || !Number.isFinite(now)) {
    return { hold: EMPTY_HOLD, anchor: null, moved: false };
  }
  // Small natural hand/camera jitter is normal. Larger displacement from
  // the START pose, or changes in apparent size, restart the three seconds.
  const moved = origin !== null && (
    Math.abs(current.cx - origin.cx) > Math.max(.015, origin.width * .13) ||
    Math.abs(current.cy - origin.cy) > Math.max(.015, origin.height * .11) ||
    Math.abs(current.width - origin.width) > origin.width * .12 ||
    Math.abs(current.height - origin.height) > origin.height * .12
  );
  const expired = previous.lastSeenAt !== null &&
    (now - previous.lastSeenAt > MAX_SAMPLE_GAP_MS || now < previous.lastSeenAt);
  const restart = !origin || moved || expired;
  return {
    hold: advanceHold(restart ? EMPTY_HOLD : previous, now, true),
    anchor: restart ? current : origin,
    moved
  };
}

export function smoothFacePoints(previous: readonly XY[] | null, next: readonly XY[], alpha = .45): XY[] {
  if (!previous || previous.length !== next.length) return next.map(p => ({ ...p }));
  return next.map((p, i) => ({
    x: previous[i].x * (1 - alpha) + p.x * alpha,
    y: previous[i].y * (1 - alpha) + p.y * alpha
  }));
}

export function clockwiseFacePath(points: readonly XY[]): string {
  if (points.length < 3) return "";
  const area2 = points.reduce((area, p, i) => {
    const q = points[(i + 1) % points.length];
    return area + p.x * q.y - q.x * p.y;
  }, 0);
  // In display coordinates, positive signed area is clockwise.
  const ordered = area2 >= 0 ? [...points] : [points[0], ...points.slice(1).reverse()];
  const fixed = (n: number) => Number(n.toFixed(1));
  let path = "M " + fixed(ordered[0].x) + " " + fixed(ordered[0].y);
  for (let i = 0; i < ordered.length; i++) {
    const n = ordered.length;
    const p0 = ordered[(i - 1 + n) % n];
    const p1 = ordered[i];
    const p2 = ordered[(i + 1) % n];
    const p3 = ordered[(i + 2) % n];
    const c1x = fixed(p1.x + (p2.x - p0.x) / 6);
    const c1y = fixed(p1.y + (p2.y - p0.y) / 6);
    const c2x = fixed(p2.x - (p3.x - p1.x) / 6);
    const c2y = fixed(p2.y - (p3.y - p1.y) / 6);
    path += " C " + c1x + " " + c1y + " " + c2x + " " + c2y +
      " " + fixed(p2.x) + " " + fixed(p2.y);
  }
  return path + " Z";
}
