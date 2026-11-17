import test from "node:test";
import assert from "node:assert/strict";
import {
  advanceHold, advanceStationaryHold, clockwiseFacePath, EMPTY_HOLD,
  projectFaceGuide, READY_HOLD_MS, smoothFacePoints, FACE_OVAL_INDICES
} from "../src/faceGuide.ts";

function sample() {
  const face=Array.from({length:478},()=>({x:.5,y:.5}));
  const set=(i,x,y)=>{face[i]={x,y};};
  set(10,.5,.13);set(152,.5,.87);set(234,.2,.45);set(454,.8,.45);
  set(4,.5,.51);set(33,.3,.42);set(133,.43,.42);set(159,.365,.405);set(145,.365,.435);
  set(362,.57,.42);set(263,.7,.42);set(386,.635,.405);set(374,.635,.435);
  set(98,.42,.58);set(327,.58,.58);set(61,.35,.69);set(291,.65,.69);
  set(172,.29,.74);set(397,.71,.74);
  set(168,.5,.38);set(17,.5,.70);set(0,.5,.685);set(13,.5,.687);set(14,.5,.697);
  return face;
}
const image={width:800,height:800};
const stage={x:0,y:0,width:300,height:420};

test("front contour comes from actual face landmarks, not a fixed-size overlay",()=>{
  const a=projectFaceGuide([sample()],image,stage);
  assert.equal(a.state,"aligned");
  assert.equal(a.points.length,FACE_OVAL_INDICES.length);
  assert.ok(a.anchor.width>.4);
  const shifted=sample().map(p=>({x:p.x+.12,y:p.y}));
  const b=projectFaceGuide([shifted],image,stage);
  assert.equal(b.state,"aligned"); // no tiny fixed outline to fit into
  assert.ok(a.points[0].x>b.points[0].x); // mirrored camera projects opposite way
  assert.notEqual(clockwiseFacePath(a.points),clockwiseFacePath(b.points));
});
test("blank scene, multiple faces and cropped head are not capture-ready",()=>{
  assert.equal(projectFaceGuide([],image,stage).state,"no-face");
  assert.equal(projectFaceGuide([sample(),sample()],image,stage).state,"multiple");
  const clipped=sample();clipped[10]={x:.5,y:.002};
  assert.notEqual(projectFaceGuide([clipped],image,stage).state,"aligned");
});
test("small and huge faces are rejected based on actual VIDEO area, not SVG proportions",()=>{
  const small=sample().map(p=>({x:.5+(p.x-.5)*.20,y:.5+(p.y-.5)*.20}));
  assert.equal(projectFaceGuide([small],image,stage).state,"too-small");
  const huge=sample().map(p=>({x:.5+(p.x-.5)*1.42,y:.5+(p.y-.5)*1.22}));
  assert.notEqual(projectFaceGuide([huge],image,stage).state,"aligned");
});
test("mirroring and object-fit:contain letterboxing follow the actual face",()=>{
  const mirrored=projectFaceGuide([sample()],image,stage,true);
  const notMirrored=projectFaceGuide([sample()],image,stage,false);
  assert.ok(Math.abs(mirrored.points[1].x+notMirrored.points[1].x-300)<.001);
  const wide=projectFaceGuide([sample()],image,{x:20,y:30,width:360,height:420},true);
  assert.equal(wide.state,"aligned");
  assert.ok(wide.points[0].x>mirrored.points[0].x);
});
test("clockwise path always begins on forehead and closes a smooth face loop",()=>{
  const cw=[{x:50,y:0},{x:100,y:50},{x:50,y:100},{x:0,y:50}];
  const ccw=[cw[0],cw[3],cw[2],cw[1]];
  const a=clockwiseFacePath(cw),b=clockwiseFacePath(ccw);
  assert.equal(a,b);
  assert.match(a,/^M 50 0 C /);
  assert.match(a,/ Z$/);
  assert.equal(clockwiseFacePath([]),"");
});
test("mild camera jitter is smoothed, larger movements reset green progress",()=>{
  const a=projectFaceGuide([sample()],image,stage).anchor;
  assert.ok(a);
  let tracking=advanceStationaryHold(EMPTY_HOLD,null,a,100,true);
  const mild={...a,cx:a.cx+.01,cy:a.cy+.01};
  tracking=advanceStationaryHold(tracking.hold,tracking.anchor,mild,900,true);
  assert.equal(tracking.moved,false);
  assert.ok(tracking.hold.progress>0);
  const large={...a,cx:a.cx+.19};
  tracking=advanceStationaryHold(tracking.hold,tracking.anchor,large,1500,true);
  assert.equal(tracking.moved,true);
  assert.equal(tracking.hold.progress,0);
  assert.equal(tracking.hold.startedAt,1500);
  const smoothed=smoothFacePoints([{x:0,y:0}],[{x:10,y:20}],.4);
  assert.deepEqual(smoothed,[{x:4,y:8}]);
});
test("three uninterrupted seconds finish the green scan without auto photography",()=>{
  assert.equal(READY_HOLD_MS,3000);
  const anchor=projectFaceGuide([sample()],image,stage).anchor;
  let tracking=advanceStationaryHold(EMPTY_HOLD,null,anchor,100,true);
  for(const time of [800,1500,2200,3099]) {
    tracking=advanceStationaryHold(tracking.hold,tracking.anchor,anchor,time,true);
  }
  assert.equal(tracking.hold.complete,false);
  tracking=advanceStationaryHold(tracking.hold,tracking.anchor,anchor,3100,true);
  assert.equal(tracking.hold.progress,1);
  assert.equal(tracking.hold.complete,true);
  tracking=advanceStationaryHold(tracking.hold,tracking.anchor,null,3150,false);
  assert.deepEqual(tracking.hold,EMPTY_HOLD);
});
test("long model pauses and new valid face restart the three-second scan",()=>{
  const anchor=projectFaceGuide([sample()],image,stage).anchor;
  let t=advanceStationaryHold(EMPTY_HOLD,null,anchor,0,true);
  t=advanceStationaryHold(t.hold,t.anchor,anchor,400,true);
  t=advanceStationaryHold(t.hold,t.anchor,anchor,1600,true);
  assert.equal(t.hold.progress,0);
  assert.equal(t.hold.startedAt,1600);
  assert.equal(advanceHold(t.hold,500,false).complete,false);
});
