import assert from "node:assert/strict";
import test from "node:test";
import { comparePhotoAnalyses } from "../src/consistency.ts";

const descriptor=(id,region,ratio,text,usable=true)=>({
  id,region,ratio,text,usable,caveat:"仅当前照片",measurement:"实验比例"
});
const first={ status:"ok", message:"local", descriptors:[
  descriptor("face.aspect","整体脸型",1.34,"面部长宽比例相对均衡"),
  descriptor("eyes.openness","眼部",.21,"眼部开合比例接近实验分类边界"),
  descriptor("mouth.width","口部",.53,"口部横向比例相对偏大"),
  descriptor("mouth.lip","唇部厚度",.15,"唇部可见厚度偏丰")
]};
const withChanges=(edits)=>({
  ...first,
  descriptors:first.descriptors.map(d=>({...d,...(edits[d.id] ?? {})}))
});

test("same photo descriptors yield no spurious category or classical source changes",()=>{
  const result=comparePhotoAnalyses(first,structuredClone(first));
  assert.ok(result);
  assert.equal(result.labelChangeCount,0);
  assert.equal(result.historicalChangeCount,0);
  assert.equal(result.historical.length,9);
  assert.ok(result.descriptors.every(d=>d.ratioDelta===0));
});

test("small ratio drift is visible numerically without falsely counting a category flip",()=>{
  const result=comparePhotoAnalyses(first,withChanges({
    "face.aspect":{ratio:1.346}
  }));
  assert.ok(result);
  assert.equal(result.labelChangeCount,0);
  assert.equal(result.historicalChangeCount,0);
  assert.equal(result.descriptors.find(d=>d.id==="face.aspect").ratioDelta,.006);
});

test("changed mouth dimensions change both the visible label and relevant historical links",()=>{
  const result=comparePhotoAnalyses(first,withChanges({
    "mouth.width":{ratio:.44,text:"口部横向比例处于中间区间"}
  }));
  assert.ok(result);
  assert.equal(result.labelChangeCount,1);
  assert.equal(result.historicalChangeCount,2);
  assert.deepEqual(result.historical.filter(d=>d.changed).map(d=>d.cardId),
    ["MY25-MOUTH-01","MY25-MOUTH-OX-01"]);
  assert.ok(result.historical.filter(d=>d.changed).every(d=>d.firstRelated&&!d.secondRelated));
});

test("lip visibility changes are not silently treated as stable",()=>{
  const result=comparePhotoAnalyses(first,withChanges({
    "mouth.lip":{usable:false,text:"唇部明显张开，不判断厚度"}
  }));
  assert.ok(result);
  assert.equal(result.labelChangeCount,1);
  assert.equal(result.historical.find(d=>d.cardId==="MY25-MOUTH-OX-01").secondRelated,false);
});

test("absent observation and failed face detection cannot count as a successful comparison",()=>{
  const partial={...first,descriptors:first.descriptors.filter(d=>d.id!=="mouth.lip")};
  const r=comparePhotoAnalyses(first,partial);
  assert.ok(r);
  assert.equal(r.descriptors.find(d=>d.id==="mouth.lip").labelChanged,true);
  assert.equal(r.descriptors.find(d=>d.id==="mouth.lip").ratioDelta,null);
  assert.equal(comparePhotoAnalyses(first,{status:"no-face",message:"none",descriptors:[]}),null);
  assert.equal(comparePhotoAnalyses({status:"poor-quality",message:"none",descriptors:[]},first),null);
});
