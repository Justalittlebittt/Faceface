import catalog from "./knowledge/maiyi-v06.json" with { type: "json" };
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

export type FaceReading = {
  heading: string;
  overview: string;
  observations: Descriptor[];
  sourceLinks: CulturalLink[];
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
  }
};

const cards = catalog.cards as SourceCard[];
const metricToDescriptor: Record<string, string> = {
  eye_aspect_ratio: "eyes.openness",
  mouth_width_norm: "mouth.width"
};

export function makeReading(analysis: Analysis, language: Language = "zh"): FaceReading | null {
  if (analysis.status !== "ok") return null;

  const byId = new Map(analysis.descriptors.map(d => [d.id, d]));
  const sourceLinks: CulturalLink[] = cards.map(card => {
    const descriptor = card.linked_metric ? byId.get(metricToDescriptor[card.linked_metric] ?? "") : undefined;
    const related = !!descriptor && card.mode === "geometry_only";
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
        ? (english ? "The observed region is related to historical wording, but the text supplies no compatible numeric cutoff. A complete traditional face type is NOT established." : "这项现代几何观察与古籍谈论的部位相关，但原书没有给出可直接套用的数值门槛，不能认定相型成立。")
        : (english ? "The required shape was not measured. A different modern geometric ratio cannot substitute for this historical condition." : "目前的特征不满足可靠观察条件；即使照片中有相关部位，也不能用其他比例替代原文条件。"),
      caveat: english ? gloss.caveat : card.caveat,
      source: card.source
    };
  });

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
    observations: analysis.descriptors.map(d => localizeDescriptor(d, language)),
    sourceLinks,
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
        "Source: Mai Yi Xiang Fa (麻衣相法), 1925 Qin Shen'an collation, vol. 1, 五官总论, PDF zero-based page " + link.source.pdf_page_zero_based,
        "Original scan: " + link.source.source_url,
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
    "【现代反思建议】",
    reading.reflection,
    "",
    "【出处及限制】",
    reading.evidenceNotice
  ];
  return parts.join("\n");
}
