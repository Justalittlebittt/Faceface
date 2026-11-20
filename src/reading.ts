import catalog from "./knowledge/maiyi-source-checked-v5.json" with { type: "json" };
import type { Analysis, Descriptor } from "./descriptors";
import { localizeDescriptor, type Language } from "./i18n.ts";
import { modernReflectionForCard, type EditorialReflection } from "./editorial.ts";

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
  conditionCount: number;
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

export type ThreeSectionsReading = {
  title: string;
  summary: string;
  caveat: string;
  parts: { id: "upper" | "middle" | "lower"; label: string; percent: number }[];
  source: SourceCard["source"];
};

export type FaceReading = {
  heading: string;
  overview: string;
  patternSummary: string;
  crossRegionStudy: { title: string; narrative: string } | null;
  observations: Descriptor[];
  sourceLinks: CulturalLink[];
  featuredLinks: CulturalLink[];
  briefInsights: string[];
  modernReflections: EditorialReflection[];
  frameworkNotes: HistoricalFramework[];
  threeSections: ThreeSectionsReading | null;
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
  },
  "MY25-FACE-ROUND-01": {
    organ: "Face", title: "Facial outline (historical text)",
    gloss: "Round and lustrous face [brief contextual gloss]",
    caveat: "Only the width-to-height direction is observed. A broad photo ratio cannot establish the complete rounded contour or luster of the original wording."
  },
  "MY25-NOSE-LONG-01": {
    organ: "Nose", title: "Nose proportions (historical verse)",
    gloss: "Long nose associated with longevity [historical belief, not fact]",
    caveat: "This is one two-dimensional ratio, not a nasal-bridge assessment, a health indicator, or a lifespan prediction."
  },
  "MY25-CHIN-WIDE-01": {
    organ: "Chin", title: "Three Talents and Three Sections",
    gloss: "Chin as Earth; broadly square [partial descriptive gloss]",
    caveat: "Jaw width relative to cheekbones does not demonstrate a square chin. This traditional description does not predict wealth."
  },
  "MY25-MOUTH-CATFISH-01": {
    organ: "Mouth", title: "Catfish-mouth illustration (historical chart)",
    gloss: "Catfish mouth: broad opening and lowered corners [partial illustrated description]",
    caveat: "The drawing additionally describes pointed corners and lips; broad mouth width plus lowered corners cannot establish the full illustration. Expression can change the photo. The text's pejorative fortune statements are historical prejudice, not an assessment of the person."
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
      return !!d && d.usable !== false &&
        d.certainty !== "borderline" && d.certainty !== "unavailable" &&
        Number.isFinite(d.ratio) &&
        (rule.operator === "gt" ? d.ratio > rule.value : d.ratio < rule.value);
    });
}

export function makeReading(analysis: Analysis, language: Language = "zh"): FaceReading | null {
  if (analysis.status !== "ok") return null;

  const byId = new Map(analysis.descriptors.map(d => [d.id, d]));
  const sourceLinks: CulturalLink[] = cards.map(card => {
    const related = observedConditions(card, byId);
    const metricUncertain = card.conditions.some(rule => {
      const d = byId.get(rule.metric);
      return !!d && (d.certainty === "borderline" ||
        d.certainty === "unavailable" || d.usable === false);
    });
    const metrics = [...new Set(card.conditions.map(rule => rule.metric))];
    const observed = metrics.map(metric => byId.get(metric)).filter((d): d is Descriptor => !!d);
    // All tested conditions are listed, including uncertainty when the mouth
    // is open. A matched subset of ratios never confirms the historic type.
    const english = language === "en";
    const gloss = englishSource[card.id];
    return {
      cardId: card.id,
      conditionCount: card.conditions.length,
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
        : metricUncertain
          ? (english
            ? "At least one measurement lies near a provisional boundary or is unusable. No historical shape link is assigned."
            : "至少一项照片指标接近实验分类边界或不可用；不触发古籍关联，也不据此认定相型。")
          : (english
            ? "The current measurement does not support even a limited directional resemblance, or the historical condition is not measurable here. No classical type is assigned."
            : "当前比例未能支持该古籍用语的局部形态方向，或者原文所需形态未测量；不据此作出相型判断。"),
      caveat: english ? gloss.caveat : card.caveat,
      historicalView: english ? card.historical_view_en : card.historical_view_zh,
      source: card.source
    };
  });

  // A phone-first report should not repeat overlapping words for the same
  // region. Prefer richer composite evidence, then source order; reserve all
  // source cards (including unsupported ones) for the expanded audit trail.
  const regionPriority: Record<string, number> = language === "en"
    ? { Face: 0, Nose: 1, Chin: 2, Eyes: 3, Mouth: 4 }
    : { "面": 0, "鼻": 1, "頦": 2, "眼": 3, "口": 4 };
  const featuredLinks = sourceLinks
    .map((link, index) => ({ link, index }))
    .filter(item => item.link.status === "related-observation")
    .sort((a, b) => b.link.conditionCount - a.link.conditionCount ||
      (regionPriority[a.link.organ] ?? 9) - (regionPriority[b.link.organ] ?? 9) ||
      a.index - b.index)
    .filter((item, index, items) =>
      items.findIndex(other => other.link.organ === item.link.organ) === index)
    .slice(0, 2)
    .map(item => item.link);

  // M14: a true cross-region paragraph only exists when TWO independently
  // source-checked, usable photo directions in DIFFERENT regions are present.
  // It is not an extra ancient compound rule or a personality inference.
  const crossRegionStudy = featuredLinks.length === 2 ? {
    title: language === "en" ? "Reading across two facial regions" : "跨部位古籍文化并读",
    narrative: language === "en"
      ? "In this photograph, " + featuredLinks[0].observation + "; separately, " +
        featuredLinks[1].observation + ". The checked text contains the independent terms \"" +
        featuredLinks[0].historicalTerm + "\" and \"" + featuredLinks[1].historicalTerm +
        "\" for these respective regions. Their combination has not been verified as a single classical type. These photo-only comparisons do not establish personality, health, fortune or life events."
      : "这张照片中分别观察到：" + featuredLinks[0].observation + "；以及：" +
        featuredLinks[1].observation + "。已核对的《麻衣相法》在不同部位分别使用「" +
        featuredLinks[0].historicalTerm + "」和「" + featuredLinks[1].historicalTerm +
        "」等外形用语。两处仅可独立作局部文化对照，尚无依据合成为一个古籍相型，也不能据此判断性格、健康、财运或人生经历。"
  } : null;

  // Select photographic descriptions from distinct visible regions. Put the
  // source-supported measurements first, then fill gaps from other regions.
  // Do NOT promote borderline/unusable measurements into a 'face pattern'.
  const sourceMetricIds = featuredLinks.flatMap(link =>
    cards.find(card => card.id === link.cardId)?.conditions.map(c => c.metric) ?? []);
  const priorityIds = [...new Set([...sourceMetricIds,
    "face.aspect", "eyes.spacing", "nose.length", "chin.height",
    "mouth.width", "jaw.width", "eyes.openness", "nose.width", "mouth.corner"] )];
  const selectedRegions = new Set<string>();
  const observedOverview: string[] = [];
  for (const id of priorityIds) {
    const d = byId.get(id);
    if (!d || d.usable === false || d.certainty === "borderline" ||
        d.certainty === "unavailable" || !Number.isFinite(d.ratio)) continue;
    const region = id.split(".")[0] === "chin" ? "jaw" : id.split(".")[0];
    if (selectedRegions.has(region)) continue;
    selectedRegions.add(region);
    observedOverview.push(localizeDescriptor(d, language).text);
    if (observedOverview.length === 4) break;
  }
  const patternSummary = observedOverview.length
    ? (language === "en" ? "Across distinct visible regions of this photo: " : "本次照片的跨部位外观观察：") +
      observedOverview.join(language === "en" ? "; " : "；") +
      (language === "en" ? ". All are provisional observations of this picture." : "。以上仅为本次照片的实验性描述。")
    : (language === "en"
      ? "No stable cross-region photo description is available; borderline or unmeasurable regions are left undecided."
      : "本次缺少足够可用的跨部位形态线索；临界或不可测部位不勉强判断。");

  const briefInsights = featuredLinks.length
    ? featuredLinks.map(link => language === "en"
      ? "This image shows: " + link.observation + ". The checked Mai Yi Xiang Fa phrase \"" +
        link.historicalTerm + "\" describes a partly similar visible shape. Historical interpretation: " +
        link.historicalView + " Only a photographic resemblance is observed, not a verified traditional classification."
      : "本次照片观察到：" + link.observation + "。其外观方向与《麻衣相法》中的「" +
        link.historicalTerm + "」有局部相似。古籍文化含义：" + link.historicalView +
        "。这只是照片中的局部形态对照，不代表完整古籍相型成立。")
    : [language === "en"
      ? "The checked historical descriptions have no sufficiently supported shape overlap in this photograph. You can still review the source notes in the detailed report; no traditional type is assigned."
      : "本次照片没有足够明确的形态线索与已核对的古籍用语建立局部关联。详细版仍保留原文与条件说明，不勉强套用传统相型。"];

  // Ancient 三停 refers to upper/middle/lower face, with true boundaries
  // such as hairline and brows. Modern 2D FaceMesh cannot capture those
  // exact boundaries; this is a PHOTO-ONLY spatial illustration with explicit
  // source attribution, never an ancient classification or prognosis.
  const historicThree = catalog.framework_notes.find(note =>
    note.id === "MY25-FRAME-THREE-01");
  const spans = analysis.threeSections;
  const validSpans = spans && [spans.upper, spans.middle, spans.lower].every(v =>
    Number.isFinite(v) && v > 0 && v < 1);
  const threeSections: ThreeSectionsReading | null = historicThree && validSpans ? (() => {
    const values = [spans.upper, spans.middle, spans.lower];
    const labels = language === "en" ? ["Upper", "Middle", "Lower"] : ["上段", "中段", "下段"];
    const ids = ["upper", "middle", "lower"] as const;
    const parts = values.map((v, i) => ({ id: ids[i], label: labels[i],
      percent: Math.round(v * 100) }));
    const largest = Math.max(...values), smallest = Math.min(...values);
    const index = values.indexOf(largest);
    const direction = largest - smallest < .08
      ? (language === "en" ? "The three plotted portions appear fairly close in size."
        : "本次照片的三个近似区段在画面中长度较接近。")
      : (language === "en"
        ? "The " + labels[index].toLowerCase() + " portion looks relatively longer in this photograph."
        : "本次照片中" + labels[index] + "的近似纵向跨度相对更长。");
    const valuesText = parts.map(part =>
      part.label + " " + part.percent + "%").join(language === "en" ? " · " : "、");
    return {
      title: language === "en" ? "Three face sections (approximate photo study)" : "面部三段比例（照片近似观察）",
      summary: (language === "en"
        ? "Approximate on-photo zones: " : "本次照片的三段近似比例：") +
        valuesText + (language === "en" ? ". " : "。") + direction,
      caveat: language === "en"
        ? "Uses upper-forehead, nose-root, nose-tip and chin landmarks. The first is not the real hairline. These are not the classic's precise Three Sections, nor a judgment of fortune."
        : "分段使用额上方、鼻根、鼻尖、颏底的模型点，其中额上方模型点不是真正发际线；不等于古籍完整三停，也不判断吉凶。",
      parts, source: historicThree.source
    };
  })() : null;

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
    patternSummary,
    crossRegionStudy,
    observations: analysis.descriptors.map(d => localizeDescriptor(d, language)),
    sourceLinks,
    featuredLinks,
    briefInsights,
    modernReflections: featuredLinks.map(link => modernReflectionForCard(link.cardId, language))
      .filter((item): item is EditorialReflection => item !== null),
    frameworkNotes,
    threeSections,
    reflection: language === "en"
      ? "These historical terms show how one tradition described appearance; they do not establish real personality or future events. Use observable evidence, not facial appearance, for important decisions."
      : "这些历史用语可以帮助理解传统相术如何描述外观，但不应被当作现实人格或未来事件的证据。需要做重要决定时，应优先依据真实行为与客观信息。",
    evidenceNotice: language === "en"
      ? "Source: Mai Yi Xiang Fa (麻衣相法), 1925 Wenming Press edition with Qin Shen'an collation. Verified scan references: volume 1 'General Discussion of the Five Features' (五官总论), PDF page 27; 'Five Mountains' (五岳), page 27; 'Four Rivers' (四渎), page 28; illustrated eye category on PDF page 66, mouth illustrations on pages 86–87, plus 'On the Face' on page 52 and 'On the Nose' on page 77 (printed volume 2); the 'Catfish-mouth' illustration in 'On the Mouth' on page 89 (printed volume 2), and 'Three Talents and Three Sections' (三才三停) on page 34 and the 'Three Sections' passage on page 35 (printed volume 1). All PDF pages are zero-based and refer to the same Wikimedia digital file labelled 第1卷. English glosses are explanatory, not an authoritative translation. Modern geometry thresholds do not originate in the book."
      : "依据：1925年文明书局秦慎安校勘《麻衣相法》，已核对卷一《五官总论》《五岳》（PDF零起页27）、《四渎》（页28），及印刷卷二《相目》《相口》图例（同一数字文件PDF零起页66、86、87、89）、卷二《论面》（页52）和《相鼻》（页77）、卷一《三才三停》（页34）及《三停》（页35）。现代几何阈值是项目实验设定，并非古籍原文；英文释义非权威译文。"
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
      ...(reading.crossRegionStudy ? [reading.crossRegionStudy.title, reading.crossRegionStudy.narrative] : []),
      ...(reading.threeSections ? [
        reading.threeSections.title,
        reading.threeSections.summary,
        reading.threeSections.caveat,
        "Original Three Sections source (not an accurate classical classification): " +
          reading.threeSections.source.volume + " / " + reading.threeSections.source.section +
          ", PDF zero-based page " + reading.threeSections.source.pdf_page_zero_based,
        "Original scan: " + reading.threeSections.source.source_url
      ] : []),
      ...reading.briefInsights,
      "",
      "MODERN REFLECTIONS (TODAY\u2019S WRITING, NOT CLAIMS ABOUT YOU)",
      ...reading.modernReflections.map(item => [
        item.theme, item.scene, "A question to consider: " + item.question,
        "Contemporary editorial prompt; not translated ancient advice or a facial personality assessment."
      ].join("\n")),
      "",
      "DETAILED OBSERVATIONS (PROVISIONAL)",
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
    ...(reading.crossRegionStudy ? [reading.crossRegionStudy.title, reading.crossRegionStudy.narrative] : []),
    ...(reading.threeSections ? [
      reading.threeSections.title,
      reading.threeSections.summary,
      reading.threeSections.caveat,
      "原书位置：" + reading.threeSections.source.volume + "《" + reading.threeSections.source.section +
        "》，PDF零起页" + reading.threeSections.source.pdf_page_zero_based,
      "扫描原件：" + reading.threeSections.source.source_url
    ] : []),
    ...reading.briefInsights,
    "",
    "【现代生活情境与反思（非古籍原文／非性格诊断）】",
    ...reading.modernReflections.map(item => [
      item.theme, item.scene, "留给你的问题：" + item.question,
      "现代编辑写作，仅供自我反思，不是根据外貌得出的人格判断。"
    ].join("\n")),
    "",
    "【详细版：全部面部形态观察（实验项）】",
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
