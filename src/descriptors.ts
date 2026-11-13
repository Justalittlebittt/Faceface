/**
 * Faceface M1: provisional, geometry-only observations.
 * The threshold bands below are NOT validated anthropometric norms, and
 * morphology is NOT evidence of character, health, fortune or life outcomes.
 * Normalized coordinates need the input image's width/height to measure distance.
 */
export type Point = { x: number; y: number; z?: number };
export type Descriptor = {
  id: string;
  region: string;
  measurement: string;
  ratio: number;
  text: string;
  caveat: string;
};
export type Analysis = {
  status: "ok" | "no-face" | "multiple-faces" | "poor-quality";
  message: string;
  descriptors: Descriptor[];
};

const empty = (status: Exclude<Analysis["status"], "ok">, message: string): Analysis =>
  ({ status, message, descriptors: [] });

function category(
  value: number, lower: number, upper: number, margin: number,
  low: string, middle: string, high: string, borderline: string
): string {
  // A measured ratio just above/below a provisional cutoff can change between
  // browsers. Prefer a neutral description instead of fabricating certainty.
  if (Math.abs(value - lower) <= margin || Math.abs(value - upper) <= margin) return borderline;
  return value < lower ? low : value > upper ? high : middle;
}

/** Pure, testable transform. Input comes from a REAL FaceLandmarker.detect() call in App.tsx. */
export function describeLandmarks(faces: readonly (readonly Point[])[], image: { width: number; height: number }): Analysis {
  if (faces.length === 0) return empty("no-face", "没有检测到清晰的人脸，请面向镜头并改善光线。");
  if (faces.length !== 1) return empty("multiple-faces", "画面出现多张人脸，请只保留一位拍摄者。");
  const face = faces[0];
  if (face.length < 455 || image.width <= 0 || image.height <= 0) {
    return empty("poor-quality", "模型数据不足，无法可靠描述面部。");
  }

  const required = [10, 152, 234, 454, 4, 33, 133, 159, 145, 362, 263, 386, 374, 98, 327, 61, 291, 172, 397];
  if (required.some(i => !face[i] || !Number.isFinite(face[i].x) || !Number.isFinite(face[i].y))) {
    return empty("poor-quality", "部分关键点缺失，请重新拍摄。");
  }
  const p = (i: number) => face[i];
  const d = (a: number, b: number): number => {
    const dx = (p(a).x - p(b).x) * image.width;
    const dy = (p(a).y - p(b).y) * image.height;
    return Math.hypot(dx, dy);
  };

  // Conservative framing checks, not a clinically calibrated head-pose estimator.
  const boundary = [p(10), p(152), p(234), p(454)];
  if (boundary.some(point => point.x < 0.025 || point.x > 0.975 || point.y < 0.025 || point.y > 0.975)) {
    return empty("poor-quality", "脸部靠近画面边缘，可能被裁切；请后退一点重拍。");
  }
  const faceWidth = d(234, 454);
  const faceHeight = d(10, 152);
  if (faceWidth < 24 || faceHeight < 24) return empty("poor-quality", "人脸太小，请靠近一点。");

  // Compare both eye centers in pixel space. Rotated heads bias the raw
  // horizontal/vertical face ratios; ask for a retake rather than guessing.
  const leftEyeY = (p(33).y + p(133).y) / 2;
  const rightEyeY = (p(362).y + p(263).y) / 2;
  const eyeSpan = d(33, 263);
  const rollRatio = Math.abs(leftEyeY - rightEyeY) * image.height / Math.max(eyeSpan, 1);
  if (rollRatio > 0.16) {
    return empty("poor-quality", "头部倾斜较明显，请保持双眼接近水平后重拍。");
  }
  const midpoint = (p(234).x + p(454).x) / 2;
  const midOffset = Math.abs(p(4).x - midpoint) / Math.max(0.001, Math.abs(p(454).x - p(234).x));
  if (midOffset > 0.19) {
    return empty("poor-quality", "面部可能明显偏转，当前仅支持接近正面的画面。");
  }

  const faceRatio = faceHeight / faceWidth;
  const eyeWidthL = d(33, 133);
  const eyeWidthR = d(362, 263);
  if (eyeWidthL < 4 || eyeWidthR < 4) return empty("poor-quality", "眼部关键点不足，请重新拍摄。");
  const eyeOpen = (d(159, 145) / eyeWidthL + d(386, 374) / eyeWidthR) / 2;
  const noseWidth = d(98, 327) / faceWidth;
  const mouthWidth = d(61, 291) / faceWidth;
  const jawWidth = d(172, 397) / faceWidth;

  const caveat = "探索阶段的比例区间，尚未经过多设备/人群标定；拍摄角度、表情与妆容可能影响结果。";
  const make = (id: string, region: string, measurement: string, ratio: number, text: string): Descriptor =>
    ({ id, region, measurement, ratio: Number(ratio.toFixed(3)), text, caveat });

  const descriptors = [
    make("face.aspect", "整体脸型", "脸部高度 / 颧部横向跨度", faceRatio,
      category(faceRatio, 1.28, 1.53, 0.02, "面部轮廓在画面中相对偏宽", "面部长宽比例相对均衡", "面部轮廓在画面中相对偏长", "脸部长宽比例接近实验分类边界，暂不判断偏宽或均衡")),
    make("eyes.openness", "眼部", "上下眼睑间距 / 横向眼宽（双眼均值）", eyeOpen,
      category(eyeOpen, 0.22, 0.32, 0.015, "当前眼部开合比例偏小", "当前眼部开合比例居中", "当前眼部开合比例偏大", "眼部开合比例接近实验分类边界，暂不判定偏小、居中或偏大")),
    make("nose.width", "鼻部", "鼻翼两侧横向跨度 / 颧部横向跨度", noseWidth,
      category(noseWidth, 0.27, 0.35, 0.012, "鼻翼横向比例相对偏窄", "鼻翼横向比例处于中间区间", "鼻翼横向比例相对偏宽", "鼻翼横向比例接近实验分类边界，本次不做宽窄分档")),
    make("mouth.width", "口部", "双侧口角距离 / 颧部横向跨度", mouthWidth,
      category(mouthWidth, 0.37, 0.48, 0.015, "口部横向比例相对偏小", "口部横向比例处于中间区间", "口部横向比例相对偏大", "口部横向比例接近实验分类边界，本次不做大小分档")),
    make("jaw.width", "下颌", "下颌两侧跨度 / 颧部横向跨度", jawWidth,
      category(jawWidth, 0.65, 0.77, 0.015, "下颌相对颧部偏窄", "下颌与颧部宽度比例居中", "下颌相对颧部偏宽", "下颌与颧部宽度比例接近实验分类边界，暂不判断偏宽或偏窄"))
  ];

  if (descriptors.some(item => !Number.isFinite(item.ratio) || item.ratio <= 0 || item.ratio > 3)) {
    return empty("poor-quality", "关键点比例异常，无法稳定描述；请重拍。");
  }
  return {
    status: "ok",
    message: "以下描述来自本次相机帧的模型关键点与实验性比例计算，不代表传统面相判词。",
    descriptors
  };
}
