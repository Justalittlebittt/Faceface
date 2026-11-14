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

test("retains original source cards and adds two independently scanned forms", () => {
  const reading = makeReading(ok);
  assert.deepEqual(reading.sourceLinks.map(x => x.cardId),
    ["MY25-EYE-01", "MY25-MOUTH-01", "MY25-NOSE-01", "MY25-MOUTH-ARC-01", "MY25-EYE-OX-01", "MY25-MOUTH-OX-01"]);
  assert.deepEqual(reading.sourceLinks.map(x=>x.source.pdf_page_zero_based), [27,27,27,86,66,87]);
  assert.ok(reading.sourceLinks.every(x => x.source.source_url.includes("commons.wikimedia.org")));
});

test("an incomplete metric never becomes a historical face-type verdict", () => {
  const reading = makeReading(ok);
  assert.deepEqual(reading.sourceLinks.map(x => x.status),
    ["related-observation", "insufficient", "insufficient", "insufficient", "insufficient", "insufficient"]);
  assert.ok(reading.sourceLinks.every(x => x.status !== "confirmed"));
  assert.match(reading.overview, /不足以判定完整的传统相型/);
});

test("no substitution of nose-wing width for classical nose bridge straightness", () => {
  const reading = makeReading(ok);
  const nose = reading.sourceLinks.find(x => x.cardId === "MY25-NOSE-01");
  assert.equal(nose.status, "insufficient");
  assert.match(nose.explanation, /不据此作出相型判断/);
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
  assert.match(text, /现代几何阈值是项目实验设定/);
});

test("historical excerpts are conditionally related only when measured direction supports them", () => {
  const onlyMouth = {
    ...ok, descriptors: descriptors.map(d => d.id === "eyes.openness"
      ? { ...d, ratio: .22, text: "眼部开合比例接近实验分类边界，暂不判定偏小、居中或偏大" }
      : d.id === "mouth.width"
        ? { ...d, ratio: .53, text: "口部横向比例相对偏大" } : d)
  };
  const reading = makeReading(onlyMouth);
  assert.deepEqual(reading.sourceLinks.map(link => link.status),
    ["insufficient", "related-observation", "insufficient", "insufficient", "insufficient", "insufficient"]);
  assert.match(reading.sourceLinks[1].explanation, /局部相似/);
  const neither = {
    ...onlyMouth, descriptors: onlyMouth.descriptors.map(d => d.id === "mouth.width"
      ? { ...d, ratio: .43, text: "口部横向比例处于中间区间" } : d)
  };
  assert.equal(makeReading(neither).sourceLinks.filter(link => link.status === "related-observation").length, 0);
});

test("expanded narrative remains cross-region rather than repeating a fixed fate verdict", () => {
  const extended = { ...ok, descriptors: [...descriptors,
    { id:"eyes.spacing",region:"双眼间距",measurement:"inter-eye",ratio:1.01,text:"双眼内眼角间距与眼宽比例居中",caveat:"实验" },
    { id:"nose.length",region:"鼻部纵向",measurement:"nose",ratio:.21,text:"照片中鼻部纵向比例处于中间区间",caveat:"实验" },
    { id:"chin.height",region:"下巴纵向",measurement:"chin",ratio:.24,text:"照片中下巴纵向比例处于中间区间",caveat:"实验" }
  ]};
  const reading = makeReading(extended);
  assert.match(reading.patternSummary, /跨部位观察/);
  assert.match(reading.patternSummary, /双眼内眼角间距/);
  assert.match(readingAsText(reading), /下巴纵向比例/);
});

test("mouth-corner source is conditional, and no complete illustrated type is confirmed", () => {
  const curve=(ratio)=>({...ok,descriptors:[
    ...descriptors,
    {id:"mouth.corner",region:"口角走势",measurement:"corner index",ratio,
      text: ratio>.55?"本次照片中双侧口角相对上扬":"本次照片中口角与唇中线接近水平",
      caveat:"当次表情可能改变"}
  ]});
  const neutral=makeReading(curve(.51)),smiling=makeReading(curve(.62));
  assert.equal(neutral.sourceLinks[3].status,"insufficient");
  assert.equal(smiling.sourceLinks[3].status,"related-observation");
  assert.equal(smiling.sourceLinks[3].historicalTerm,"仰月口");
  assert.match(smiling.sourceLinks[3].caveat,/笑容和表情/);
  assert.doesNotMatch(readingAsText(smiling),/已确认仰月口/);
});
test("non-personal Five Mountains and Four Rivers notes remain source-traceable in both languages", () => {
  const zh=makeReading(ok,"zh"),en=makeReading(ok,"en");
  assert.deepEqual(zh.frameworkNotes.map(x=>x.id),
    ["MY25-FRAME-MOUNTAINS-01","MY25-FRAME-RIVERS-01"]);
  assert.deepEqual(zh.frameworkNotes.map(x=>x.source.pdf_page_zero_based),[27,28]);
  assert.deepEqual(en.frameworkNotes.map(x=>x.id),zh.frameworkNotes.map(x=>x.id));
  assert.match(readingAsText(zh),/古籍取象背景/);
  assert.match(readingAsText(zh),/鼻為濟/);
  assert.match(readingAsText(en,"en"),/HISTORICAL SYSTEM/);
  assert.match(readingAsText(en,"en"),/Four Rivers/);
  assert.match(readingAsText(en,"en"),/vol\. 1|卷一/);
});

test("ox-mouth source only relates when BOTH width and reliable lip thickness agree", () => {
  const shape=(width,lip,usable=true)=>({...ok,descriptors:[
    ...descriptors.map(d=>d.id==="mouth.width"?{...d,ratio:width,text:"口部横向比例相对偏大"}:d),
    {id:"mouth.lip",region:"唇部厚度",measurement:"lip height / mouth width",ratio:lip,
      text:usable?"本次照片中唇部可见厚度相对偏丰":"照片中嘴唇有明显张开，暂不判断唇部厚薄",usable,caveat:"当次照片"}
  ]});
  const final=(x)=>makeReading(x).sourceLinks.find(link=>link.cardId==="MY25-MOUTH-OX-01");
  assert.equal(final(shape(.53,.15)).status,"related-observation");
  assert.equal(final(shape(.43,.15)).status,"insufficient");
  assert.equal(final(shape(.53,.06)).status,"insufficient");
  assert.equal(final(shape(.53,.15,false)).status,"insufficient");
  const matched=final(shape(.53,.15));
  assert.match(matched.observation,/口部横向比例/);
  assert.match(matched.observation,/唇部可见厚度/);
  assert.match(matched.historicalView,/传统说法/);
  assert.doesNotMatch(matched.historicalView,/你.*富/);
});

test("ox-eye illustration has a separate eye-opening condition", () => {
  const large={...ok,descriptors:descriptors.map(d=>d.id==="eyes.openness"
    ? {...d,ratio:.38,text:"当前眼部开合比例偏大"}:d)};
  const ox=makeReading(large).sourceLinks.find(link=>link.cardId==="MY25-EYE-OX-01");
  assert.equal(ox.status,"related-observation");
  assert.match(ox.historicalView,/历史的象形比喻/);
  const borderline={...ok,descriptors:descriptors.map(d=>d.id==="eyes.openness"
    ? {...d,ratio:.329,text:"眼部开合比例接近实验分类边界"}:d)};
  assert.equal(makeReading(borderline).sourceLinks.find(x=>x.cardId==="MY25-EYE-OX-01").status,"insufficient");
});

test("missing or unusable metrics never trigger composite historical labels", () => {
  const bare={...ok,descriptors:descriptors.filter(x=>x.id!=="mouth.width")};
  const reading=makeReading(bare);
  assert.equal(reading.sourceLinks.find(x=>x.cardId==="MY25-MOUTH-OX-01").status,"insufficient");
  assert.equal(reading.sourceLinks.find(x=>x.cardId==="MY25-NOSE-01").status,"insufficient");
  assert.match(readingAsText(reading),/卷二/);
});

test("historic interpretation remains attributed culture rather than predicting user wealth", () => {
  const src=makeReading(ok);
  assert.equal(src.sourceLinks.length,6);
  const en=readingAsText(makeReading(ok,"en"),"en");
  assert.match(en,/What the historic text says/);
  assert.match(en,/Original wording: 牛口/);
  assert.match(en,/PDF zero-based page 87/);
  const zh=readingAsText(src);
  assert.match(zh,/古籍文化解读（非现实预测）/);
  assert.match(zh,/吉祥寓意/);
});

test("short report prioritizes composite evidence and diverse face regions", () => {
  const d=[
    ...descriptors.map(item => item.id === "mouth.width"
      ? {...item,ratio:.54,text:"口部横向比例相对偏大"} : item),
    {id:"mouth.corner",region:"口角走势",measurement:"corner",ratio:.60,text:"本次照片中双侧口角相对上扬",caveat:"表达影响"},
    {id:"mouth.lip",region:"唇部厚度",measurement:"lip",ratio:.16,text:"本次照片中唇部可见厚度相对偏丰",usable:true,caveat:"表情影响"}
  ];
  const reading=makeReading({...ok,descriptors:d});
  assert.ok(reading.sourceLinks.filter(item=>item.status==="related-observation").length >= 4);
  assert.deepEqual(reading.featuredLinks.map(item=>item.cardId),
    ["MY25-MOUTH-OX-01","MY25-EYE-01"]);
  assert.equal(new Set(reading.featuredLinks.map(item=>item.organ)).size,2);
  assert.equal(reading.featuredLinks[0].conditionCount,2);
  assert.equal(reading.briefInsights.length,2);
  assert.match(reading.briefInsights[0],/牛口/);
  assert.match(reading.briefInsights[1],/或細長/);
});

test("no-match report stays useful without manufacturing ancient classifications", () => {
  const withoutMatches={...ok,descriptors:descriptors.map(d => {
    if(d.id==="eyes.openness")return {...d,ratio:.25,text:"当前眼部开合比例居中"};
    return d;
  })};
  const reading=makeReading(withoutMatches);
  assert.equal(reading.featuredLinks.length,0);
  assert.equal(reading.briefInsights.length,1);
  assert.match(reading.briefInsights[0],/不勉强套用传统相型/);
  assert.equal(reading.sourceLinks.length,6);
  const asText=readingAsText(reading);
  assert.match(asText,/详细版：全部面部形态观察/);
  assert.match(asText,/条件不足/);
});

test("download export has a genuinely short narrative before detailed measurements", () => {
  const bilingual=["zh","en"];
  for(const lang of bilingual){
    const reading=makeReading(ok,lang);
    const exported=readingAsText(reading,lang);
    const detailedStart=lang==="en"?"DETAILED OBSERVATIONS":"【详细版：全部面部形态观察";
    const start=lang==="en"?"SHORT REPORT":"【简洁报告】";
    const short=exported.split(start)[1].split(detailedStart)[0];
    assert.ok(short.length>30);
    assert.equal((short.match(/face ratio/g)||[]).length,0);
    assert.ok(!short.includes("jaw ratio"));
    assert.equal(reading.featuredLinks.length,1);
    assert.ok(exported.includes("牛口")); // source archive is always traceable
    assert.ok(exported.includes(reading.evidenceNotice));
  }
});

test("bilingual highlights identify identical evidence and remain limited to two", () => {
  const zh=makeReading(ok,"zh");
  const en=makeReading(ok,"en");
  assert.deepEqual(zh.featuredLinks.map(x=>x.cardId),en.featuredLinks.map(x=>x.cardId));
  assert.deepEqual(zh.featuredLinks.map(x=>x.status),en.featuredLinks.map(x=>x.status));
  assert.match(en.briefInsights[0],/Only a photographic resemblance/);
  assert.ok(zh.featuredLinks.length<=2);
});
