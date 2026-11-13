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
  set(168,.5,.38);set(17,.5,.70);
  return face;
}
const image = { width: 800, height: 800 };

test("reports no-face and multiple-face states rather than guessing", () => {
  assert.equal(describeLandmarks([], image).status, "no-face");
  assert.equal(describeLandmarks([sample(), sample()], image).status, "multiple-faces");
});
test("outputs eight independently measured features spanning five face regions", () => {
  const result = describeLandmarks([sample()], image);
  assert.equal(result.status, "ok");
  assert.deepEqual(result.descriptors.map(d => d.region), ["整体脸型", "眼部", "鼻部", "口部", "下颌", "双眼间距", "鼻部纵向", "下巴纵向"]);
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

test("rejects an obviously tilted head before assigning face ratio labels", () => {
  const face = sample();
  // Simulate the right eye being noticeably lower, without changing face width.
  face[362] = { x: .57, y: .55 };
  face[263] = { x: .70, y: .55 };
  assert.equal(describeLandmarks([face], image).status, "poor-quality");
});

test("rejects missing required landmark coordinates", () => {
  const face = sample();
  face[98] = { x: Number.NaN, y: .58 };
  assert.equal(describeLandmarks([face], image).status, "poor-quality");
});

test("changing observed eye and nose ratios changes the resulting descriptions", () => {
  const changed = sample();
  changed[98] = { x: .35, y: .58 };
  changed[327] = { x: .65, y: .58 };
  changed[159] = { x: .365, y: .38 };
  changed[145] = { x: .365, y: .46 };
  changed[386] = { x: .635, y: .38 };
  changed[374] = { x: .635, y: .46 };
  const original = describeLandmarks([sample()], image);
  const adjusted = describeLandmarks([changed], image);
  assert.equal(adjusted.status, "ok");
  for (const region of ["眼部", "鼻部"]) {
    assert.notEqual(original.descriptors.find(d => d.region === region).text,
      adjusted.descriptors.find(d => d.region === region).text);
  }
});

test("faces too small for meaningful pixel geometry are not labelled", () => {
  assert.equal(describeLandmarks([sample()], { width: 20, height: 20 }).status, "poor-quality");
});

test("nearly identical eye geometry on opposite sides of a provisional cutoff stays uncertain", () => {
  function eyesAtRatio(ratio) {
    const face = sample();
    const halfHeight = ratio * .13 / 2;
    for (const [upper, lower, x] of [[159, 145, .365], [386, 374, .635]]) {
      face[upper] = { x, y: .42 - halfHeight };
      face[lower] = { x, y: .42 + halfHeight };
    }
    return face;
  }
  const left = describeLandmarks([eyesAtRatio(.219)], image);
  const right = describeLandmarks([eyesAtRatio(.221)], image);
  assert.equal(left.status, "ok");
  assert.equal(right.status, "ok");
  const a = left.descriptors.find(d => d.id === "eyes.openness");
  const b = right.descriptors.find(d => d.id === "eyes.openness");
  assert.equal(a.ratio, .219);
  assert.equal(b.ratio, .221);
  assert.equal(a.text, b.text);
  assert.match(a.text, /分类边界/);
});

test("additional eye-gap, nose-length and chin-height fields respond independently", () => {
  const before = describeLandmarks([sample()], image);
  const face = sample();
  face[133] = { x: .40, y: .42 };
  face[362] = { x: .60, y: .42 };
  face[168] = { x: .5, y: .32 };
  face[17] = { x: .5, y: .62 };
  const after = describeLandmarks([face], image);
  assert.equal(before.status, "ok");
  assert.equal(after.status, "ok");
  for (const id of ["eyes.spacing", "nose.length", "chin.height"]) {
    const a = before.descriptors.find(d => d.id === id);
    const b = after.descriptors.find(d => d.id === id);
    assert.ok(a && b);
    assert.notEqual(a.ratio, b.ratio);
  }
});

test("newly required landmarks cannot be silently hallucinated", () => {
  const face = sample();
  face[168] = { x: Number.NaN, y: .39 };
  assert.equal(describeLandmarks([face], image).status, "poor-quality");
});
