/**
 * Faceface's short life reading: culturally styled, explicitly speculative
 * interpretations for currently source-checked PARTIAL APPEARANCE parallels.
 *
 * The old book has NOT been verified as describing any given user's past,
 * personal temperament or future. Past and future prose here is ORIGINAL
 * editorial storytelling, NOT a quotation or historical prediction from
 * the source. No invented past event, diagnosis, or factual certainty.
 */
import type { Language } from "./i18n.ts";

export type LifeReadingCard = {
  sourceCardId: string;
  title: string;
  temperament: string;
  retrospective: string;
  outlook: string;
  attribution: "speculative-modern-reading";
};

type Text = Omit<LifeReadingCard,"sourceCardId"|"attribution">;
const interpretations: Record<string,Record<Language,Text>> = {
  "MY25-EYE-01": {
    en: {title:"A thoughtful rhythm", temperament:"This image can evoke the theme of someone who values a moment of observation before speaking. It is a storytelling theme, not a trait measured from your eyes.", retrospective:"Looking back, you may recognize a conversation in which waiting to speak helped you understand the situation more clearly—or a time when you wished you had paused.", outlook:"An upcoming conversation may be a useful opportunity to hear the whole story before deciding what to say."},
    zh: {title:"先观察，再表达", temperament:"这幅眼部意象可以引出“先观察、再表达”的性情主题；这不是从眼睛测出的真实人格。", retrospective:"回想过去，你或许经历过一次先听后说反而看清问题的讨论，也可能有过希望自己慢一点表达的时刻。", outlook:"接下来遇到重要沟通时，不妨先了解全貌，再决定怎样表达。"}
  },
  "MY25-EYE-OX-01": {
    en: {title:"An open outlook", temperament:"The expressive-eye imagery suggests curiosity as a theme worth exploring, not a conclusion about your personality.", retrospective:"There may have been a time when a new idea or a chance encounter changed how you saw a familiar problem.", outlook:"A different perspective may become useful when a new project or acquaintance arrives."},
    zh: {title:"保持开放的眼光", temperament:"大眼的传统象形可以引出好奇、开放的主题，但不等于已认定你的性格。", retrospective:"你也许能回忆起一次因为新想法或偶遇而改变看法的经历。", outlook:"下一次遇到陌生的人或事，换个角度观察也许会带来启发。"}
  },
  "MY25-MOUTH-01": {
    en: {title:"The art of expression", temperament:"A broad-mouth shape can become a metaphor for expression and conversation, without claiming to reveal your communication style.", retrospective:"You might recall a moment when saying what you meant directly resolved a misunderstanding—or when the words were harder to find.", outlook:"In a coming discussion, clarity about what matters to you could make the exchange more productive."},
    zh: {title:"表达的分寸", temperament:"宽阔口形可以作为表达与交流的象征，但不能由此判断你现实中的沟通性格。", retrospective:"回想过去，也许有一次清楚说出需求化解了误会，或有一次你觉得话到嘴边却说不清。", outlook:"将来遇到重要讨论时，先想明白自己的重点，可能会让沟通更顺畅。"}
  },
  "MY25-MOUTH-ARC-01": {
    en: {title:"The warmth of a first impression", temperament:"A lifted-mouth illustration invites a theme of warmth in social encounters; a passing expression cannot establish a permanent trait.", retrospective:"Perhaps there was a meeting that felt awkward at first but became easier after a small, friendly gesture.", outlook:"A future meeting could be an opportunity to help others feel welcome without forcing a particular impression."},
    zh: {title:"第一印象中的温度", temperament:"上扬口形引出待人和气的意象，但一瞬间的表情并不代表稳定的性格。", retrospective:"你也许遇到过最初有些拘谨、后来因一句友好问候而放松的相识。", outlook:"下一次认识新朋友时，轻松真诚的一句话也许比刻意表现更有效。"}
  },
  "MY25-MOUTH-OX-01": {
    en: {title:"The meaning of abundance", temperament:"This mouth illustration carried auspicious livelihood imagery in the old source. It offers a cultural theme of security and sufficiency, not a verified financial profile.", retrospective:"You may recognize a period when a steady routine or help from others made ordinary life feel more secure.", outlook:"In the next chapter, planning around steady needs may be more useful than chasing dramatic promises of luck."},
    zh: {title:"富足与安稳", temperament:"古籍的“牛口”图式带有衣食昌隆的吉祥寓意；这里借此谈安稳与满足，并非确认现实财运。", retrospective:"回想过去，你也许经历过一段因生活渐趋稳定或有人支持而更踏实的时期。", outlook:"接下来比起等待突如其来的好运，更值得经营稳定的生活节奏与可执行的计划。"}
  },
  "MY25-FACE-ROUND-01": {
    en: {title:"Finding your balance", temperament:"A rounded contour becomes a metaphor for flexibility and balance in this contemporary interpretation, not an assessment of temperament.", retrospective:"You may remember needing to balance two commitments that both mattered to you.", outlook:"A change of priorities could be a good moment to protect time for what matters most."},
    zh: {title:"找到自己的平衡", temperament:"圆润轮廓在现代叙事中可以借喻圆融和平衡，但并不由此推断真实的性格。", retrospective:"你可能曾遇到过两件都舍不得放下的事，需要在它们之间重新分配精力。", outlook:"下一次调整生活重心时，主动安排时间可能比事事兼顾更有帮助。"}
  },
  "MY25-NOSE-LONG-01": {
    en: {title:"The long view", temperament:"The original phrase connects nose length with longevity as an old belief. Here 'long' is only a metaphor for considering long-term choices, not a health or lifespan forecast.", retrospective:"Perhaps you once made a decision whose consequences only became clear months later.", outlook:"An upcoming choice may benefit from considering what will still matter after the immediate excitement fades."},
    zh: {title:"把目光放长", temperament:"古籍“鼻长有寿”属于历史相术说法；这里仅借“长远”作比喻，不预测健康或寿命。", retrospective:"过去或许有一项选择，直到几个月后你才真正看见它的影响。", outlook:"接下来遇到一项决定时，试着想想短暂热情过去之后，什么仍然重要。"}
  },
  "MY25-CHIN-WIDE-01": {
    en: {title:"A steady foundation", temperament:"The historical Earth imagery suggests steadiness as a metaphor, not proof that the person is dependable or strong-willed.", retrospective:"You might recall a period when having a routine, a trusted person, or a clear boundary helped you through change.", outlook:"When plans shift again, a small reliable habit could offer a useful place to start."},
    zh: {title:"稳固的支点", temperament:"古籍把颏部喻为“地”，现代可借“稳定”作生活意象，但不能由此外貌推断意志或责任心。", retrospective:"你也许曾在变化较多的一段时间里，依靠习惯或一位可信的人找到安定感。", outlook:"未来计划有变时，一件稳定的小习惯也许能帮助你重新建立节奏。"}
  },
  "MY25-MOUTH-CATFISH-01": {
    en: {title:"Seeing past appearances", temperament:"This historical illustration also carried harsh value judgments. Those judgments should not be transferred to a living person.", retrospective:"Think of a time an initial impression of somebody proved incomplete once you knew their story.", outlook:"A future encounter may reward a little patience before forming a firm opinion."},
    zh: {title:"第一印象以外", temperament:"这一历史口形图示含有旧式贬义评价，不应移用为对现代个人的评判。", retrospective:"回想一次你在了解更多经历后，对某个人改变了第一印象的时刻。", outlook:"今后遇到陌生人，不急于下判断，也许能让你看到更多真实的细节。"}
  }
};

export function buildSpeculativeLifeReading(
  sourceCardIds: string[], language: Language
): LifeReadingCard[] {
  return [...new Set(sourceCardIds)].slice(0,2).flatMap(sourceCardId => {
    const text=interpretations[sourceCardId]?.[language];
    return text?[{sourceCardId,...text,attribution:"speculative-modern-reading" as const}]:[];
  });
}
