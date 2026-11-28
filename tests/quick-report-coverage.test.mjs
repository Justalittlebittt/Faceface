import test from "node:test";
import assert from "node:assert/strict";
import { makeReading, shortLifeReadingAsText } from "../src/reading.ts";
const baseline = {"eyes.openness":.27,"eyes.spacing":.98,"mouth.width":.42,"mouth.corner":.5,"mouth.lip":.085,"face.aspect":1.4,"nose.length":.20,"nose.width":.31,"jaw.width":.71,"chin.height":.24};
const scenarios = [
 ["middle",{},[]],
 ["narrow eyes",{"eyes.openness":.18},["MY25-EYE-01"]],
 ["wide eyes",{"eyes.openness":.37},["MY25-EYE-OX-01"]],
 ["wide full mouth",{"mouth.width":.53,"mouth.lip":.15},["MY25-MOUTH-OX-01"]],
 ["long nose wide jaw",{"nose.length":.28,"jaw.width":.83},["MY25-NOSE-LONG-01","MY25-CHIN-WIDE-01"]],
 ["narrow mouth short nose",{"mouth.width":.32,"nose.length":.13},[]],
 ["downward mouth",{"mouth.corner":.40},[]]
];
for(const [name,patch,expected] of scenarios) test("quick report: "+name,()=>{
 const descriptors=Object.entries({...baseline,...patch}).map(([id,ratio])=>({id,ratio,region:id.split(".")[0],measurement:id,text:id+" "+ratio,caveat:"synthetic",certainty:"clear"}));
 for(const language of ["en","zh"]){
 const reading=makeReading({status:"ok",message:"synthetic",descriptors},language);
 assert.ok(reading);
 assert.deepEqual(reading.featuredLinks.map(x=>x.cardId).sort(),[...expected].sort());
 assert.ok(reading.patternSummary.length>0);
 assert.ok(shortLifeReadingAsText(reading,language).includes(reading.patternSummary));
 assert.equal(reading.lifeNarratives.length,expected.length);
 }
});
