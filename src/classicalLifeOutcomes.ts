import raw from "./knowledge/maiyi-historical-life-outcomes-v1.json" with { type: "json" };
import catalog from "./knowledge/maiyi-source-checked-v5.json" with { type: "json" };
import type { Language } from "./i18n.ts";

/** Historical assertions are not the same thing as face measurements or
 * modern-editorial temperament/past/future stories. All archived source
 * claims are only shown in Detailed Reading, without treating observed
 * approximate photo features as a confirmed traditional face category. */
export type ClassicalLifeOutcome = {
  id: string;
  sourceCardId: string;
  domain: string;
  historicalQuote: string;
  historicalShapePhrase: string;
  explanation: string;
  source: {
    section: string;
    volume: string;
    source_url: string;
    pdf_page_zero_based: number;
    edition: string;
  };
  sourceCardMatchStatus: "related-observation" | "insufficient";
  appliesToUserAsFact: false;
  isVerifiedFuturePrediction: false;
};

type Match = { cardId: string; status: "related-observation" | "insufficient" };

export function archivedClassicalLifeOutcomes(
  matches: readonly Match[], language: Language
): ClassicalLifeOutcome[] {
  const matchesById = new Map(matches.map(x=>[x.cardId,x.status]));
  if (matchesById.size !== matches.length) throw new Error("Duplicate source IDs in face reading");
  const catalogById = new Map(catalog.cards.map(x=>[x.id,x]));
  const used = new Set<string>();
  return raw.records.map(row => {
    if (used.has(row.id)) throw new Error("Duplicate historical outcome claim ID");
    used.add(row.id);
    const card = catalogById.get(row.source_card_id);
    if (!card || !matchesById.has(row.source_card_id)) {
      throw new Error("Life outcome phrase without a current source-checked card");
    }
    if (card.source.pdf_page_zero_based !== row.source_scan_pdf_page_zero_based ||
        card.source.section !== row.source_book_section ||
        row.appropriate_use !== "detailed_reference_only" ||
        row.verified_for_personal_photo_prediction !== false ||
        row.source_entire_historical_type_photo_match_confirmed !== false ||
        !card.source.source_url.startsWith("https://commons.wikimedia.org/wiki/File:")) {
      throw new Error("Invalid historical quote provenance or false personal outcome promotion");
    }
    if (!row.historical_claim_phrase || !row.source_exact_phrase ||
        !row.source_exact_phrase.includes(row.historical_claim_phrase)) {
      throw new Error("Historical outcome is not literal to the cited phrase");
    }
    if (row.id==="MY-OUTCOME-1925-001" &&
        card.source_phrase !== row.source_exact_phrase) {
      throw new Error("Short verse claim must reproduce the checked shape phrase");
    }
    if (row.id==="MY-OUTCOME-1925-002" &&
        !card.historical_view_zh.includes(row.source_exact_phrase)) {
      throw new Error("Traditional auspicious phrase not in the existing checked source gloss");
    }
    return {
      id:row.id,
      sourceCardId:row.source_card_id,
      domain:row.domain,
      historicalQuote:row.source_exact_phrase,
      historicalShapePhrase:row.historical_shape_phrase,
      explanation: language==="en"?row.plain_english:row.plain_chinese,
      source: {
        section:card.source.section, volume:card.source.volume,
        source_url:card.source.source_url,
        pdf_page_zero_based:card.source.pdf_page_zero_based,
        edition:card.source.edition
      },
      sourceCardMatchStatus:matchesById.get(row.source_card_id)!,
      appliesToUserAsFact:false as const,
      isVerifiedFuturePrediction:false as const
    };
  });
}
