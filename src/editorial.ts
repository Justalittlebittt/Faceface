/**
 * Contemporary, optional reflection prompts inspired by SOURCE-CHECKED
 * historical shape imagery. Not source quotations, personality evidence,
 * trait predictions, or user-specific facts.
 *
 * Deliberately keep them separate from the scan-verified historical gloss.
 */
import type { Language } from "./i18n";

export type EditorialReflection = {
  sourceCardId: string;
  theme: string;
  scene: string;
  question: string;
  provenance: "modern-editorial-reflection";
};

type Narrative = Omit<EditorialReflection, "sourceCardId" | "provenance">;

const editorial: Record<string, Record<Language, Narrative>> = {
  "MY25-EYE-01": {
    en: {
      theme: "A moment to observe",
      scene: "Picture a conversation where everyone has something to say. Sometimes the most useful contribution arrives after a moment of listening, when the details start to connect.",
      question: "When you have something important to say, do you prefer to think it through first—or speak while you work it out?"
    },
    zh: {
      theme: "先观察，再表达",
      scene: "想象一次大家争着发言的讨论。有时真正有用的一句话，反而是在听完细节、想明白之后才出现。",
      question: "遇到重要事情，你更习惯先观察思考，还是边交流边整理思路？"
    }
  },
  "MY25-EYE-OX-01": {
    en: {
      theme: "Curiosity in everyday life",
      scene: "A new place, an unfamiliar idea, a detail nobody has mentioned yet—curiosity can turn a routine day into something worth exploring.",
      question: "What was the last small detail that made you stop and ask another question?"
    },
    zh: {
      theme: "给好奇心留一点空间",
      scene: "一个陌生的地方、一个新点子，或是没人留意的小细节，都可能让普通的一天多出一点新发现。",
      question: "最近一次让你忍不住多问一句“为什么”的小事是什么？"
    }
  },
  "MY25-MOUTH-01": {
    en: {
      theme: "Finding your own voice",
      scene: "In a group discussion, the useful moment is not always speaking the loudest. Sometimes it is finding one clear sentence that moves the conversation forward.",
      question: "When you want to be understood, do you lead with your conclusion or build up to it?"
    },
    zh: {
      theme: "找到自己的表达方式",
      scene: "在多人讨论里，重要的不一定是谁说得最大声。有时一句讲得清楚的话，就能让事情向前走一步。",
      question: "需要让别人理解你时，你习惯先说结论，还是慢慢解释来龙去脉？"
    }
  },
  "MY25-MOUTH-ARC-01": {
    en: {
      theme: "The tone you bring",
      scene: "A quick greeting can make an unfamiliar room feel less distant. Yet even a friendly expression changes from moment to moment; it does not define a person.",
      question: "What helps you feel at ease when meeting someone new?"
    },
    zh: {
      theme: "人与人之间的第一句话",
      scene: "一句轻松的问候，有时就能让陌生的场合没那么拘谨。但表情会随情境变化，并不能定义一个人。",
      question: "认识新朋友时，什么事情最容易让你放松下来？"
    }
  },
  "MY25-MOUTH-OX-01": {
    en: {
      theme: "What does a good life mean?",
      scene: "Old writings sometimes describe abundance as having enough for daily life. Today, that image can invite a different question: which kinds of security and comfort really matter to you?",
      question: "If you could make one part of everyday life feel more abundant, which would you choose?"
    },
    zh: {
      theme: "怎样才算生活富足",
      scene: "古书常用衣食丰足来描绘吉祥。放在今天，也可以换个角度想：什么样的安稳与从容才真正让你感到富足？",
      question: "如果能让日常生活中的一件事更丰盈，你最想改善哪一件？"
    }
  },
  "MY25-FACE-ROUND-01": {
    en: {
      theme: "Balance is a moving target",
      scene: "Balance rarely looks the same every week. One day might need a bold decision; another calls for quiet time and space to reset.",
      question: "Where in your routine would a little more balance make the biggest difference?"
    },
    zh: {
      theme: "平衡不是固定的样子",
      scene: "生活的平衡并不要求每天一样。有时需要果断行动，有时需要一点安静的时间，重新整理节奏。",
      question: "你现在最希望在哪件日常小事上找到更舒服的平衡？"
    }
  },
  "MY25-NOSE-LONG-01": {
    en: {
      theme: "Thinking in longer chapters",
      scene: "The classical phrase links appearance with longevity as a historical belief, not a health prediction. As a modern metaphor, a long view can simply mean giving important choices more time.",
      question: "Is there a decision that might benefit from looking a year ahead instead of only at tomorrow?"
    },
    zh: {
      theme: "把目光放长一点",
      scene: "原书把外形与寿数联系，是历史上的相术观念，不是健康预测。若把“长远”当成今天的比喻，它提醒我们给重要选择多一点时间。",
      question: "有没有一件事，值得你不只考虑明天，而是想想一年后的自己？"
    }
  },
  "MY25-CHIN-WIDE-01": {
    en: {
      theme: "Finding solid ground",
      scene: "The old Earth metaphor evokes steadiness. In daily life, a steady foundation might be a reliable routine, a trusted friend, or simply knowing what matters most.",
      question: "What small habit helps you feel grounded when plans suddenly change?"
    },
    zh: {
      theme: "给自己一个稳稳的支点",
      scene: "古籍里把下颏比作“地”。在现代生活中，稳定也许是一套可靠的习惯、一位可信的朋友，或是清楚知道自己最重视什么。",
      question: "计划突然变化时，哪一个小习惯最能帮你稳住节奏？"
    }
  },
  "MY25-MOUTH-CATFISH-01": {
    en: {
      theme: "Beyond first impressions",
      scene: "Some historical descriptions attached harsh judgments to appearance. A moment of reflection can point in the opposite direction: an expression in a photograph is not the whole person.",
      question: "When has getting to know someone changed your first impression?"
    },
    zh: {
      theme: "第一印象之外",
      scene: "古籍有时会把外貌和带偏见的评价联系在一起。今天反而值得问问：一张照片里的表情，真的能代表一个人的全部吗？",
      question: "你有没有在深入了解一个人之后，彻底改变过最初的印象？"
    }
  }
};

export function modernReflectionForCard(cardId: string, language: Language): EditorialReflection | null {
  const content = editorial[cardId]?.[language];
  return content ? {
    sourceCardId: cardId,
    ...content,
    provenance: "modern-editorial-reflection"
  } : null;
}
