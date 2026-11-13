import assert from "node:assert/strict";
import test from "node:test";
import { copy, t, localizeDescriptor, localizeAnalysisMessage } from "../src/i18n.ts";
import { makeReading, readingAsText } from "../src/reading.ts";

const descriptors = [
  { id:"face.aspect", region:"整体脸型", measurement:"face ratio", ratio:1.29, text:"脸部长宽比例接近实验分类边界，暂不判断偏宽或均衡", caveat:"实验阈值" },
  { id:"eyes.openness", region:"眼部", measurement:"eye ratio", ratio:.22, text:"眼部开合比例接近实验分类边界，暂不判定偏小、居中或偏大", caveat:"实验阈值" },
  { id:"nose.width", region:"鼻部", measurement:"nose ratio", ratio:.30, text:"鼻翼横向比例处于中间区间", caveat:"实验阈值" },
  { id:"mouth.width", region:"口部", measurement:"mouth ratio", ratio:.52, text:"口部横向比例相对偏大", caveat:"实验阈值" },
  { id:"jaw.width", region:"下颌", measurement:"jaw ratio", ratio:.80, text:"下颌相对颧部偏宽", caveat:"实验阈值" },
  { id:"eyes.spacing", region:"双眼间距", measurement:"inter-eye ratio", ratio:1.01, text:"双眼内眼角间距与眼宽比例居中", caveat:"实验阈值" },
  { id:"nose.length", region:"鼻部纵向", measurement:"nose ratio", ratio:.20, text:"照片中鼻部纵向比例处于中间区间", caveat:"实验阈值" },
  { id:"chin.height", region:"下巴纵向", measurement:"chin ratio", ratio:.25, text:"照片中下巴纵向比例处于中间区间", caveat:"实验阈值" },
  { id:"mouth.corner", region:"口角走势", measurement:"corner index", ratio:.61, text:"本次照片中双侧口角相对上扬", caveat:"当次表情" }
];
const analysis = { status:"ok", message:"以下描述来自本次相机帧的模型关键点与实验性比例计算，不代表传统面相判词。", descriptors };

test("both language catalogs contain the same nonempty keys", () => {
  assert.deepEqual(Object.keys(copy.en).sort(),Object.keys(copy.zh).sort());
  for(const lang of ["en","zh"])assert.ok(Object.values(copy[lang]).every(v=>typeof v==="string"&&v.length));
  assert.equal(t("en","switchLanguage"),"中文");
  assert.equal(t("zh","switchLanguage"),"English");
});
test("translated descriptors preserve identities, metrics and boundary uncertainty", () => {
  for(const descriptor of descriptors){
    const en=localizeDescriptor(descriptor,"en");
    assert.equal(en.id,descriptor.id);assert.equal(en.ratio,descriptor.ratio);
    assert.notEqual(en.text,descriptor.text);
    assert.doesNotMatch(en.text,/Untranslated/);
    assert.deepEqual(localizeDescriptor(descriptor,"zh"),descriptor);
  }
});
test("English camera guidance covers no-face, multi-face and tilt failures", () => {
  const cases=[
    ["no-face","没有检测到清晰的人脸，请面向镜头并改善光线。","No clear face"],
    ["multiple-faces","画面出现多张人脸，请只保留一位拍摄者。","More than one face"],
    ["poor-quality","头部倾斜较明显，请保持双眼接近水平后重拍。","head appears tilted"]
  ];
  for(const [status,message,expected] of cases)
    assert.match(localizeAnalysisMessage({status,message,descriptors:[]}, "en"),new RegExp(expected,"i"));
});
test("English and Chinese reports share source IDs and retain original historical text", () => {
  const en=makeReading(analysis,"en"),zh=makeReading(analysis,"zh");
  assert.deepEqual(en.sourceLinks.map(c=>c.cardId),zh.sourceLinks.map(c=>c.cardId));
  assert.deepEqual(en.sourceLinks.map(c=>c.status),zh.sourceLinks.map(c=>c.status));
  assert.ok(en.sourceLinks.every(c=>c.historicalTerm&&c.historicalGloss));
  assert.equal(en.sourceLinks[2].status,"insufficient");
  assert.match(en.sourceLinks[2].explanation,/No classical type is assigned/);
  const englishText=readingAsText(en,"en");
  for(const phrase of ["SHORT REPORT","Original wording: 或細長","not a certified translation","PDF zero-based page 27","MODERN REFLECTION"])
    assert.ok(englishText.includes(phrase),phrase);
  const chineseText=readingAsText(zh,"zh");
  assert.match(chineseText,/【简洁报告】/);
  assert.match(chineseText,/扫描 PDF 零起页27/);
  assert.match(englishText,/仰月口/);
  assert.match(englishText,/PDF zero-based page 86/);
  assert.match(englishText,/Four Rivers/);
  assert.match(chineseText,/仰月口/);
});
