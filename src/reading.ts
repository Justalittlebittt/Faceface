import catalog from "./knowledge/maiyi-source-checked-v1.json" with { type: "json" };
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
  }
};

const cards = catalog.cards as SourceCard[];
const metricToDescriptor: Record<string, string> = {
  eye_aspect_ratio: "eyes.openness",
  mouth_width_norm: "mouth.width",
  mouth_corner_index: "mouth.corner"
};

export function makeReading(analysis: Analysis, language: Language = "zh"): FaceReading | null {
  if (analysis.status !== "ok") return null;

  const byId = new Map(analysis.descriptors.map(d => [d.id, d]));
  const sourceLinks: CulturalLink[] = cards.map(card => {
    const descriptor = card.linked_metric ? byId.get(metricToDescriptor[card.linked_metric] ?? "") : undefined;
    // A common organ is NOT enough for a historical cross-reference.
    // At most a *partial* directional resemblance is recorded. The historic
    // full condition (e.g. square AND broad mouth) is never auto-confirmed.
    // These bands mirror provisional M1 ratio thresholds, not book criteria.
    const related = !!descriptor && card.mode === "geometry_only" &&
      ((card.id === "MY25-EYE-01" && descriptor.ratio < 0.205) ||
       (card.id === "MY25-MOUTH-01" && descriptor.ratio > 0.495) ||
       (card.id === "MY25-MOUTH-ARC-01" && descriptor.ratio > 0.550));
    const english = language === "en";
    const gloss = englishSource[card.id];
    return {
      cardId: card.id,
      organ: english ? gloss.organ : card.organ,
      historicalTerm: card.source_phrase,
      historicalGloss: english ? gloss.gloss : undefined,
      traditionalName: english ? gloss.title : card.traditional_name,
      status: related ? "related-observation" : "insufficient",
      observation: descriptor ? localizeDescriptor(descriptor, language).text :
        (english ? "The required historical shape was not measured in this photograph." : "本次尚未测量这个古籍词语要求的具体形态。"),
      explanation: related
        ? (english
          ? "Only one measured direction loosely resembles a phrase from the book. The full historical condition, its exceptions and a calibrated numeric standard are not established."
          : "本次比例仅与古籍词语中的一个外观方向存在局部相似；原文完整形态、例外条件和数值标准均未满足核查，不能认定相型成立。")
        : (english
          ? "The current measurement does not support even a limited directional resemblance, or the historical condition is not measurable here. No classical type is assigned."
          : "当前比例未能支持该古籍用语的局部形态方向，或者原文所需形态未测量；不据此作出相型判断。"),
      caveat: english ? gloss.caveat : card.caveat,
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
      ? "Source: Mai Yi Xiang Fa (麻衣相法), 1925 Wenming Press edition with Qin Shen'an collation, vol. 1, 'General Discussion of the Five Features' (五官总论), printed page 14 (PDF zero-based page 27). English glosses are explanatory only, not an authoritative translation. Modern numeric thresholds do not originate in the book."
      : "依据：1925年文明书局秦慎安校勘《麻衣相法》卷一《五官总论》，原书页十四（扫描 PDF 零起页27）。当代几何阈值是项目实验设定，并非古籍原文。"
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
