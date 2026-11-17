/**
 * Local-only, two-photo repeatability comparison.
 *
 * This compares observations for two images that the participant explicitly
 * chooses. It cannot establish whether both images depict the same person,
 * nor validate morphology, ancient face types, or personal traits.
 *
 * Inputs contain only Faceface descriptors; raw pixels, landmark arrays and
 * identity embeddings are neither retained nor exported.
 */
import type { Analysis, Descriptor } from "./descriptors.ts";
import { makeReading } from "./reading.ts";

export type DescriptorDifference = {
  id: string;
  first: Descriptor;
  second: Descriptor | null;
  ratioDelta: number | null;
  labelChanged: boolean; // includes provisional reliability status changes
};

export type SectionDifference = {
  id: "upper" | "middle" | "lower";
  firstPercent: number | null;
  secondPercent: number | null;
  deltaPoints: number | null; // percentage points, not percent change
};

export type HistoricalDifference = {
  cardId: string;
  historicalTerm: string;
  firstRelated: boolean;
  secondRelated: boolean;
  changed: boolean;
};

export type PhotoConsistency = {
  descriptors: DescriptorDifference[];
  historical: HistoricalDifference[];
  labelChangeCount: number;
  historicalChangeCount: number;
  threeSections: SectionDifference[] | null;
};

// These are PHOTO-ONLY zones, not the historical hairline-based 三停.
// Requiring a valid normalized triplet avoids reporting nonsensical percentages.
function validSections(parts: Analysis["threeSections"]): parts is NonNullable<Analysis["threeSections"]> {
  return !!parts && [parts.upper, parts.middle, parts.lower].every(n =>
    Number.isFinite(n) && n > 0 && n < 1) &&
    Math.abs(parts.upper + parts.middle + parts.lower - 1) <= 0.02;
}

export function comparePhotoAnalyses(first: Analysis, second: Analysis): PhotoConsistency | null {
  if (first.status !== "ok" || second.status !== "ok") return null;

  const newDescriptors = new Map(second.descriptors.map(d => [d.id, d]));
  const descriptors = first.descriptors.map(d => {
    const current = newDescriptors.get(d.id) ?? null;
    return {
      id: d.id,
      first: d,
      second: current,
      ratioDelta: current && Number.isFinite(current.ratio) && Number.isFinite(d.ratio)
        ? Number(Math.abs(current.ratio - d.ratio).toFixed(3)) : null,
      labelChanged: !current || d.text !== current.text ||
        (d.usable !== false) !== (current.usable !== false) ||
        d.certainty !== current.certainty
    };
  });

  const oldReading = makeReading(first, "zh");
  const newReading = makeReading(second, "zh");
  if (!oldReading || !newReading) return null;
  const newer = new Map(newReading.sourceLinks.map(link => [link.cardId, link]));
  const historical = oldReading.sourceLinks.map(link => {
    const current = newer.get(link.cardId);
    const firstRelated = link.status === "related-observation";
    const secondRelated = current?.status === "related-observation";
    return {
      cardId: link.cardId,
      historicalTerm: link.historicalTerm,
      firstRelated,
      secondRelated,
      changed: firstRelated !== secondRelated
    };
  });

  const firstZones = validSections(first.threeSections) ? first.threeSections : null;
  const secondZones = validSections(second.threeSections) ? second.threeSections : null;
  const threeSections: SectionDifference[] | null = firstZones || secondZones
    ? (["upper", "middle", "lower"] as const).map(id => {
        const a = firstZones?.[id] ?? null;
        const b = secondZones?.[id] ?? null;
        return {
          id,
          firstPercent: a === null ? null : Math.round(a * 1000) / 10,
          secondPercent: b === null ? null : Math.round(b * 1000) / 10,
          deltaPoints: a === null || b === null ? null : Math.round(Math.abs(a - b) * 1000) / 10
        };
      }) : null;

  return {
    descriptors,
    historical,
    labelChangeCount: descriptors.filter(d => d.labelChanged).length,
    historicalChangeCount: historical.filter(item => item.changed).length,
    threeSections
  };
}
