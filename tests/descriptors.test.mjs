import assert from "node:assert/strict";
import test from "node:test";
import { describeLandmarks } from "../src/descriptors.ts";

// These are synthetic geometry tests, NOT proof of real-device inference.
function sample() {
  const face = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5 }));
  const set = (id, x, y) => { face[id] = { x, y }; };
  set(10,.5,.15);set(152,.5,.85);set(234,.2,.45);set(454,.8,.45);set(4,.5,.51);
  set(33,.3,.42);set(133,.43,.42);set(159,.365,.405);set(145,.365,.435);
  set(362,.57,.42);set(263,.7,.42);set(386,.635,.405);set(374,.635,.435);
  set(98,.42,.58);set(327,.58,.58);set(61,.35,.69);set(291,.65,.69);
  set(172,.29,.74);set(397,.71,.74);
  return face;
}
const image = { width: 800, height: 800 };

test("reports no-face and multiple-face states rather than guessing", () => {
  assert.equal(describeLandmarks([], image).status, "no-face");
  assert.equal(describeLandmarks([sample(), sample()], image).status, "multiple-faces");
});
test("outputs five independently measured regions from valid geometry", () => {
  const result = describeLandmarks([sample()], image);
  assert.equal(result.status, "ok");
  assert.deepEqual(result.descriptors.map(d => d.region), ["整体脸型", "眼部", "鼻部", "口部", "下颌"]);
  assert.ok(result.descriptors.every(d => d.ratio > 0 && d.text.length > 0 && d.measurement.length > 0));
});
test("repeated input is deterministic without using personality inference", () => {
  assert.deepEqual(describeLandmarks([sample()], image), describeLandmarks([sample()], image));
});
test("flags likely cropped faces", () => {
  const face = sample(); face[10] = { x:.5, y:.001 };
  assert.equal(describeLandmarks([face], image).status, "poor-quality");
});
test("flags strong left/right framing asymmetry", () => {
  const face = sample(); face[4] = { x:.83, y:.51 };
  assert.equal(describeLandmarks([face], image).status, "poor-quality");
});
