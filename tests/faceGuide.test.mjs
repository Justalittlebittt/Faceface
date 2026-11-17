import test from "node:test";
import assert from "node:assert/strict";
import { advanceHold, checkFrontGuide, EMPTY_HOLD, READY_HOLD_MS } from "../src/faceGuide.ts";

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
const svg={x:0,y:0,width:300,height:420};

test("fits a valid near-frontal face to the actual outline, not an ellipse",()=>{
  const result=checkFrontGuide([sample()],image,stage,svg);
  assert.equal(result.state,"aligned");
  assert.ok(result.coverage>=.85);
});
test("a blank scene and multiple people are not capture-ready",()=>{
  assert.equal(checkFrontGuide([],image,stage,svg).state,"no-face");
  assert.equal(checkFrontGuide([sample(),sample()],image,stage,svg).state,"multiple");
});
test("shifting the face outside the outline immediately rejects alignment",()=>{
  const shifted=sample().map(p=>({x:p.x+.18,y:p.y}));
  assert.notEqual(checkFrontGuide([shifted],image,stage,svg).state,"aligned");
});
test("video letterboxing and mirroring change where the oval appears on the stage",()=>{
  const result=checkFrontGuide([sample()],image,{x:10,y:30,width:360,height:420},
    {x:40,y:30,width:300,height:420},true);
  assert.equal(result.state,"aligned");
});
test("three continuous seconds unlock readiness, never trigger a shutter",()=>{
  assert.equal(READY_HOLD_MS,3000);
  let hold=EMPTY_HOLD;
  for(const now of [100,950,1800,2650,3099]){
    hold=advanceHold(hold,now,true);
  }
  assert.equal(hold.complete,false);
  hold=advanceHold(hold,3100,true);
  assert.equal(hold.complete,true);
  assert.equal(hold.progress,1);
  hold=advanceHold(hold,3110,false);
  assert.equal(hold.complete,false);
  assert.equal(hold.startedAt,null);
});
test("lost detection, long sampling gaps and time reversal reset the three-second hold",()=>{
  let hold=advanceHold(EMPTY_HOLD,100,true);
  hold=advanceHold(hold,500,true);
  hold=advanceHold(hold,1800,true);
  assert.equal(hold.progress,0);
  hold=advanceHold(hold,2100,true);
  assert.ok(hold.progress>0);
  hold=advanceHold(hold,2000,true);
  assert.equal(hold.progress,0);
  hold=advanceHold(hold,2600,false);
  assert.deepEqual(hold,EMPTY_HOLD);
});
