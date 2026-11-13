import assert from "node:assert/strict";
import test from "node:test";
import { makeReading, readingAsText } from "../src/reading.ts";

const descriptors = [
  { id: "face.aspect", region: "整体脸型", measurement: "face ratio", ratio: 1.4, text: "面部长宽比例相对均衡", caveat: "仅技术观察" },
  { id: "eyes.openness", region: "眼部", measurement: "eye ratio", ratio: .2, text: "当前眼部开合比例偏小", caveat: "表情会影响" },
  { id: "nose.width", region: "鼻部", measurement: "nose ratio", ratio: .31, text: "鼻翼横向比例处于中间区间", caveat: "角度会影响" },
  { id: "mouth.width", region: "口部", measurement: "mouth ratio", ratio: .39, text: "口部横向比例处于中间区间", caveat: "表情会影响" },
  { id: "jaw.width", region: "下颌", measurement: "jaw ratio", ratio: .71, text: "下颌与颧部宽度比例居中", caveat: "角度会影响" }
];
const ok = { status: "ok", message: "geometry data", descriptors };

test("no readings generated for absent, multiple, or low-quality faces", () => {
  for (const status of ["no-face", "multiple-faces", "poor-quality"]) {
    assert.equal(makeReading({ status, message: "retake", descriptors: [] }), null);
  }
});

test("imports first three V0.6 source cards with traceable edition and page", () => {
  const reading = makeReading(ok);
  assert.deepEqual(reading.sourceLinks.map(x => x.cardId),
    ["MY25-EYE-01", "MY25-MOUTH-01", "MY25-NOSE-01"]);
  assert.ok(reading.sourceLinks.every(x => x.source.pdf_page_zero_based === 27));
  assert.ok(reading.sourceLinks.every(x => x.source.source_url.includes("commons.wikimedia.org")));
});

test("an incomplete metric never becomes a historical face-type verdict", () => {
  const reading = makeReading(ok);
  assert.deepEqual(reading.sourceLinks.map(x => x.status),
    ["related-observation", "related-observation", "insufficient"]);
  assert.ok(reading.sourceLinks.every(x => x.status !== "confirmed"));
  assert.match(reading.overview, /不足以判定完整的传统相型/);
});

test("no substitution of nose-wing width for classical nose bridge straightness", () => {
  const reading = makeReading(ok);
  const nose = reading.sourceLinks.find(x => x.cardId === "MY25-NOSE-01");
  assert.equal(nose.status, "insufficient");
  assert.match(nose.explanation, /不能用其他比例替代原文条件/);
});

test("report preserves observed differences without inventing personality scores", () => {
  const changed = { ...ok, descriptors: descriptors.map(x =>
    x.id === "eyes.openness" ? { ...x, text: "当前眼部开合比例偏大", ratio: .4 } : x) };
  const a = makeReading(ok), b = makeReading(changed);
  assert.notEqual(readingAsText(a), readingAsText(b));
  assert.equal(a.sourceLinks[0].historicalTerm, b.sourceLinks[0].historicalTerm);
});

test("downloadable text includes concise/detailed source and explicit limitations", () => {
  const text = readingAsText(makeReading(ok));
  assert.match(text, /简洁报告/);
  assert.match(text, /文化材料/);
  assert.match(text, /梁柱端直/);
  assert.match(text, /条件不足/);
  assert.match(text, /1925年文明书局/);
  assert.match(text, /扫描 PDF 零起页27/);
  assert.match(text, /当代几何阈值是项目实验设定/);
});
