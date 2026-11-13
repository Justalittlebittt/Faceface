import catalog from "./knowledge/maiyi-v06.json";
import type { Analysis, Descriptor } from "./descriptors";

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

const cards = catalog.cards as SourceCard[];
const metricToDescriptor: Record<string, string> = {
  eye_aspect_ratio: "eyes.openness",
  mouth_width_norm: "mouth.width"
};

export function makeReading(analysis: Analysis): FaceReading | null {
  if (analysis.status !== "ok") return null;

  const byId = new Map(analysis.descriptors.map(d => [d.id, d]));
  const sourceLinks: CulturalLink[] = cards.map(card => {
    const descriptor = card.linked_metric ? byId.get(metricToDescriptor[card.linked_metric] ?? "") : undefined;
    const related = !!descriptor && card.mode === "geometry_only";
    return {
      cardId: card.id,
      organ: card.organ,
      historicalTerm: card.source_phrase,
      traditionalName: card.traditional_name,
      status: related ? "related-observation" : "insufficient",
      observation: descriptor?.text ?? "本次尚未测量这个古籍词语要求的具体形态。",
      explanation: related
        ? "这项现代几何观察与古籍谈论的部位相关，但原书没有给出可直接套用的数值门槛，不能认定相型成立。"
        : "目前的特征不满足可靠观察条件；即使照片中有相关部位，也不能用其他比例替代原文条件。",
      caveat: card.caveat,
      source: card.source
    };
  });

  // Do not transform measured morphology into purported personal history,
  // disposition, capability, health, moral attributes, destiny or wealth.
  return {
    heading: "面部观察与传统文化对照",
    overview: "本次在照片中形成 " + analysis.descriptors.length +
      " 项实验性形态描述，其中 " +
      sourceLinks.filter(link => link.status === "related-observation").length +
      " 项可联系到已核对的古籍形态用语，但都不足以判定完整的传统相型。",
    observations: analysis.descriptors,
    sourceLinks,
    reflection: "这些历史用语可以帮助理解传统相术如何描述外观，但不应被当作现实人格或未来事件的证据。需要做重要决定时，应优先依据真实行为与客观信息。",
    evidenceNotice: "依据：1925年文明书局秦慎安校勘《麻衣相法》卷一《五官总论》，原书页十四（扫描 PDF 零起页27）。当代几何阈值是项目实验设定，并非古籍原文。"
  };
}

export function readingAsText(reading: FaceReading): string {
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
