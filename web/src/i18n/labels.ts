import type { MessageKey } from "./messages";

/** The API names story kinds and topics in English ("a market day"). These maps give each a catalog key so the screens
 * can show them in the site language; a name we do not know is shown as the API wrote it. */
const TOPIC_KEYS: Record<string, MessageKey> = {
  "a market day": "topic.market", "a birthday party": "topic.birthday", "a rainy day": "topic.rain",
  "a lost key": "topic.key", "a new pet": "topic.pet", "a trip by train": "topic.train",
  "cooking dinner": "topic.cooking", "a day at school": "topic.school", "a visit to a friend's house": "topic.friend",
  "a walk in the park": "topic.park", "a surprise gift": "topic.gift", "a busy morning": "topic.morning",
  "a day at the beach": "topic.beach", "fixing something at home": "topic.fixing",
  "a quiet evening at home": "topic.evening", "a bus ride": "topic.bus", "a picnic": "topic.picnic",
  "a snowy morning": "topic.snow", "a small garden": "topic.garden", "a new neighbor": "topic.neighbor",
  "a long walk home": "topic.home",
};
const TYPE_KEYS: Record<string, MessageKey> = {
  story: "storyType.story", narration: "storyType.narration", dialogue: "storyType.dialogue", diary: "storyType.diary",
  letter: "storyType.letter", place: "storyType.place", routine: "storyType.routine", anecdote: "storyType.anecdote",
};
type T = (key: MessageKey) => string;
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const topicLabel = (t: T, topic: string): string => (TOPIC_KEYS[topic] ? t(TOPIC_KEYS[topic]) : cap(topic));
export const typeLabel = (t: T, type: string): string => (TYPE_KEYS[type] ? t(TYPE_KEYS[type]) : cap(type));
export const TOPIC_NAMES = Object.keys(TOPIC_KEYS);
