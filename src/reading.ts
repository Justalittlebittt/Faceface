import catalog from "./knowledge/maiyi-source-checked-v2.json" with { type: "json" };
import type { Analysis, Descriptor } from "./descriptors";
import { localizeDescriptor, type Language } from "./i18n.ts";

/**
 * M2 seed: source-linked cultural notes, not historical trait classifiers.
 * The selected V0.6 cards expressly forbid converting our uncalibrated
 * geometry ratios into claims that a complete classical face type is present.
 */
export type CulturalStatus = "related-observation" | "insufficient";

type SourceCard = {
  id: string;
  organ: string;
  traditional_name: string;
  source_phrase: string;
  modern_observation: string;
  mode: string;
  linked_metric: string | null;
  conclusion_from_metric_allowed: boolean;
  caveat: string;
  conditions: { metric: string; operator: "gt" | "lt"; value: number }[];
  historical_view_zh: string;
  historical_view_en: string;
  source: {
    work: string;
    edition: string;
    volume: string;
    section: string;
    pdf_page_zero_based: number;
    source_url: string;
  };
};

export type CulturalLink = {
  cardId: string;
  organ: string;
  historicalTerm: string;
  historicalGloss?: string;
  traditionalName: string;
  status: CulturalStatus;
  observation: string;
  explanation: string;
  caveat: string;
  historicalView: string;
  source: SourceCard["source"];
};

export type HistoricalFramework = {
  id: string;
  title: string;
  quote: string;
  explanation: string;
  source: SourceCard["source"];
};

export type FaceReading = {
  heading: string;
  overview: string;
  patternSummary: string;
  observations: Descriptor[];
  sourceLinks: CulturalLink[];
  frameworkNotes: HistoricalFramework[];
  reflection: string;
  evidenceNotice: string;
};

const englishSource: Record<string, { organ: string; title: string; gloss: string; caveat: string }> = {
  "MY25-EYE-01": {
    organ: "Eyes", title: "Observation Officer (historical term)",
    gloss: "Or slender and long [descriptive gloss]",
    caveat: "Modern eyelid-opening ratios cannot establish the ancient text's shape criteria."
  },
  "MY25-MOUTH-01": {
    organ: "Mouth", title: "Intake Officer (historical term)",
    gloss: "The mouth should be square and broad [descriptive gloss]",
    caveat: "Mouth width alone does not establish the shape described in the classical text."
  },
  "MY25-NOSE-01": {
    organ: "Nose", title: "Discernment Officer (historical term)",
    gloss: "The bridge should be upright and straight [descriptive gloss]",
    caveat: "Nostril width cannot stand in for a direct observation of the entire nasal bridge."
  },
  "MY25-MOUTH-ARC-01": {
    organ: "Mouth", title: "Illustrated mouth shapes (historical chart)",
    gloss: "Upturned crescent-shaped mouth [illustration label; explanatory gloss]",
    caveat: "The illustration depicts an entire mouth shape. A still photo only measures current mouth-corner tilt, which changes with smiling and cannot confirm the illustrated type."
  },
  "MY25-EYE-OX-01": {
    organ: "Eyes", title: "Ox-eye illustration (historical chart)",
    gloss: "Ox eyes: large eyes with rounded pupils [interpretive gloss]",
    caveat: "Only the ratio of eyelid opening to width is measured; an ancient animal-shaped eye chart is not fully established."
  },
  "MY25-MOUTH-OX-01": {
    organ: "Mouth", title: "Ox-mouth illustration (historical chart)",
    gloss: "Ox mouth: thick and full lips [interpretive gloss]",
    caveat: "Two photographic metrics can align locally, but opening the mouth, expression, cosmetics and lens angle change the observed shape."
  }
};

const cards = catalog.cards as SourceCard[];
// Every condition is an experimental *observable direction*, not a numeric
// standard claimed by the 1925 classic. Source cards with zero conditions
// must never match automatically.
function observedConditions(
  card: SourceCard,
  byId: Map<string, Descriptor>
): boolean {
  return card.mode === "geometry_only" && card.conditions.length > 0 &&
    card.conditions.every(rule => {
      const d = byId.get(rule.metric);
      return !!d && d.usable !== false && Number.isFinite(d.ratio) &&
        (rule.operator === "gt" ? d.ratio > rule.value : d.ratio < rule.value);
    });
}

export function makeReading(analysis: Analysis, language: Language = "zh"): FaceReading | null {
  if (analysis.status !== "ok") return null;

  const byId = new Map(analysis.descriptors.map(d => [d.id, d]));
  const sourceLinks: CulturalLink[] = cards.map(card => {
    const related = observedConditions(card, byId);
    const metrics = [...new Set(card.conditions.map(rule => rule.metric))];
    const observed = metrics.map(metric => byId.get(metric)).filter((d): d is Descriptor => !!d);
    // All tested conditions are listed, including uncertainty when the mouth
    // is open. A matched subset of ratios never confirms the historic type.
    const english = language === "en";
    const gloss = englishSource[card.id];
    return {
      cardId: card.id,
      organ: english ? gloss.organ : card.organ,
      historicalTerm: card.source_phrase,
      historicalGloss: english ? gloss.gloss : undefined,
      traditionalName: english ? gloss.title : card.traditional_name,
      status: related ? "related-observation" : "insufficient",
      observation: observed.length
        ? observed.map(item => localizeDescriptor(item, language).text).join(english ? "; " : "；")
        : (english ? "The required historical shape was not measured in this photograph." : "本次尚未测量这个古籍词语要求的具体形态。"),
      explanation: related
        ? (english
          ? "One or more photo measurements show a limited resemblance to the historic description. The complete classical type and its exceptions have NOT been established."
          : "本次照片中一项或多项形态方向与古籍词语局部相似；仍不足以认定完整古籍相型，也不代表古籍存在这些现代数值标准。")
        : (english
          ? "The current measurement does not support even a limited directional resemblance, or the historical condition is not measurable here. No classical type is assigned."
          : "当前比例未能支持该古籍用语的局部形态方向，或者原文所需形态未测量；不据此作出相型判断。"),
      caveat: english ? gloss.caveat : card.caveat,
      historicalView: english ? card.historical_view_en : card.historical_view_zh,
      source: card.source
    };
  });

  const frameworkNotes: HistoricalFramework[] = catalog.framework_notes.map(note => ({
    id: note.id,
    title: language === "en" ? note.title_en : note.title_zh,
    quote: note.quote,
    explanation: language === "en" ? note.explanation_en : note.explanation_zh,
    source: note.source
  }));

  // Do not transform measured morphology into purported personal history,
  // disposition, capability, health, moral attributes, destiny or wealth.
  return {
    heading: language === "en" ? "Facial observations and historical references" : "面部观察与传统文化对照",
    overview: language === "en"
      ? "This photograph yielded " + analysis.descriptors.length + " provisional geometric observations. " +
        sourceLinks.filter(link => link.status === "related-observation").length +
        " relate loosely to checked historical wording, but none proves a complete classical face type."
      : "本次在照片中形成 " + analysis.descriptors.length +
        " 项实验性形态描述，其中 " +
        sourceLinks.filter(link => link.status === "related-observation").length +
        " 项可联系到已核对的古籍形态用语，但都不足以判定完整的传统相型。",
    patternSummary: (() => {
      const chosen = ["face.aspect", "eyes.spacing", "nose.length", "chin.height"]
        .map(id => byId.get(id)).filter((d): d is Descriptor => !!d)
        .map(d => localizeDescriptor(d, language).text);
      return (language === "en" ? "Across the face: " : "跨部位观察：") + chosen.join(language === "en" ? "; " : "；") +
        (language === "en" ? ". These describe this photo only." : "。以上仅描述本次照片。");
    })(),
    observations: analysis.descriptors.map(d => localizeDescriptor(d, language)),
    sourceLinks,
    frameworkNotes,
    reflection: language === "en"
      ? "These historical terms show how one tradition described appearance; they do not establish real personality or future events. Use observable evidence, not facial appearance, for important decisions."
      : "这些历史用语可以帮助理解传统相术如何描述外观，但不应被当作现实人格或未来事件的证据。需要做重要决定时，应优先依据真实行为与客观信息。",
    evidenceNotice: language === "en"
      ? "Source: Mai Yi Xiang Fa (麻衣相法), 1925 Wenming Press edition with Qin Shen'an collation. Verified scan references: volume 1 'General Discussion of the Five Features' (五官总论), PDF page 27; 'Five Mountains' (五岳), page 27; 'Four Rivers' (四渎), page 28; illustrated eye category in printed volume 2 page 66, and illustrated mouth categories in printed volume 2 pages 86–87 (PDF pages all zero-based, within the Wikimedia digital file labelled 第1卷). English glosses are explanatory, not an authoritative translation. Modern geometry thresholds do not originate in the book."
      : "依据：1925年文明书局秦慎安校勘《麻衣相法》，已核对卷一《五官总论》《五岳》（PDF零起页27）、《四渎》（页28），及印刷卷二《相目》《相口》图例（同一数字文件PDF零起页66、86、87）。现代几何阈值是项目实验设定，并非古籍原文；英文释义非权威译文。"
  };
}

export function readingAsText(reading: FaceReading, language: Language = "zh"): string {
  if (language === "en") {
    const sections = [
      "Faceface — " + reading.heading,
      "Historical-cultural preview only. Not a scientific personality, health or destiny analysis.",
      "",
      "SHORT REPORT",
      reading.overview,
      reading.patternSummary,
      "",
      ...reading.observations.map(d => d.region + ": " + d.text),
      "",
      "HISTORICAL REFERENCES (NOT CONFIRMED FACE TYPES)",
      ...reading.sourceLinks.map(link => [
        link.organ + " / " + link.traditionalName,
        "Original wording: " + link.historicalTerm,
        "English explanation (not a certified translation): " + (link.historicalGloss ?? ""),
        "Match status: " + (link.status === "related-observation" ? "Related observation only" : "Insufficient evidence"),
        "This image: " + link.observation,
        link.explanation,
        "What the historic text says (not a factual prediction): " + link.historicalView,
        "Limit: " + link.caveat,
        "Source: Mai Yi Xiang Fa (麻衣相法), " + link.source.edition + ", " +
          link.source.volume + " / " + link.source.section + ", PDF zero-based page " + link.source.pdf_page_zero_based,
        "Original scan: " + link.source.source_url,
        ""
      ].join("\n")),
      "HISTORICAL SYSTEM (BACKGROUND, NOT PERSONALIZED MATCHES)",
      ...reading.frameworkNotes.map(note => [
        note.title,
        "Source words: " + note.quote,
        note.explanation,
        "Location: " + note.source.volume + " / " + note.source.section + ", PDF zero-based page " + note.source.pdf_page_zero_based,
        "Original scan: " + note.source.source_url,
        ""
      ].join("\n")),
      "MODERN REFLECTION (NOT AN ANCIENT QUOTE)",
      reading.reflection,
      "",
      "SOURCES AND LIMITS",
      reading.evidenceNotice
    ];
    return sections.join("\n");
  }
  const parts = [
    "Faceface — " + reading.heading,
    "文化参考／技术验证：不用于科学人格、健康或命运判断。",
    "",
    "【简洁报告】",
    reading.overview,
    reading.patternSummary,
    "",
    ...reading.observations.map(d => d.region + "：" + d.text),
    "",
    "【与古籍对应的文化材料】",
    ...reading.sourceLinks.map(link => [
      link.organ + "（" + link.traditionalName + "）：" + link.historicalTerm,
      "状态：" + (link.status === "related-observation" ? "相关观察／不能确认古籍相型" : "条件不足／不做判断"),
      "本次观察：" + link.observation,
      link.explanation,
      "古籍文化解读（非现实预测）：" + link.historicalView,
      "限制：" + link.caveat,
      "出处：" + link.source.edition + "，" + link.source.volume + "《" +
        link.source.section + "》，扫描 PDF 零起页" + link.source.pdf_page_zero_based,
      "原始文件：" + link.source.source_url,
      ""
    ].join("\n")),
    "【古籍取象背景（不是个人相型匹配）】",
    ...reading.frameworkNotes.map(note => [
      note.title,
      "原文短语：" + note.quote,
      note.explanation,
      "原书位置：" + note.source.volume + "《" + note.source.section + "》，PDF 零起页" + note.source.pdf_page_zero_based,
      "扫描原件：" + note.source.source_url,
      ""
    ].join("\n")),
    "【现代反思建议】",
    reading.reflection,
    "",
    "【出处及限制】",
    reading.evidenceNotice
  ];
  return parts.join("\n");
}
