import type { components } from "./schema";

export type Schemas = components["schemas"];
export type User = Schemas["UserOut"];
export type Word = Schemas["WordOut"];
export type WordPage = Schemas["WordPage"];
export type UploadResult = Schemas["UploadResult"];
export type LanguageInfo = Schemas["LanguageOut"];
export type Health = Schemas["HealthOut"];
export type Meta = Schemas["MetaOut"];
export type Policy = Schemas["PolicyOut"];
export type Preferences = Schemas["PreferencesOut"];
export type ChatReply = Schemas["ChatOut"];
export type ToolCall = Schemas["ToolCallOut"];
export type StoryOptions = Schemas["StoryOptionsOut"];
/** The learner's difficulty choice: a preset name, or "custom" with their own numbers. Left out = no tier. */
export interface DifficultyChoice { difficulty?: string; length?: number; own_words?: number; uncommon_pct?: number }
export type MyModel = { enabled: boolean; configured: boolean; model: string | null; base_url: string | null; key_last4: string | null; has_key: boolean };
export type GeneratedStory = Schemas["GeneratedStoryOut"];
export type SavedStory = Schemas["StoryFull"];
export type StoryPage = Schemas["StoryPage"];
export type StoryCard = Schemas["StoryCard"];
export type FlashcardSet = Schemas["FlashcardSet"];
export type ClozeSet = Schemas["ClozeSet"];
export type ClozeItem = Schemas["ClozeItem"];
export type WordSet = Schemas["SetOut"];
export type Pronunciation = Schemas["PronounceOut"];
export type Translation = Schemas["TranslateOut"];
export type SetList = Schemas["SetList"];
export type ChoiceSet = Schemas["ChoiceSet"];
export type PosSet = Schemas["PosSet"];
export type PosCard = Schemas["PosCard"];
export type DictationSet = Schemas["DictationSet"];
export type StarterPackList = Schemas["StarterPackList"];
export type StarterAdded = Schemas["StarterAdded"];
export type PracticeProgress = Schemas["ProgressOut"];
export interface Answer { word_id: number; correct: boolean }
export type ChoiceCard = Schemas["ChoiceOut"];
/** Which words to show or practise: every word, the General set, or one set by id (sent as "all", "general" or the number). */
export type SetFilter = "all" | "general" | number;
export interface DefineResult { defined: number; failed: number; remaining: number }
