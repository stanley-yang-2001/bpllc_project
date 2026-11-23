import type { components } from "./schema";

export type Schemas = components["schemas"];
export type User = Schemas["UserOut"];
export type Word = Schemas["WordOut"];
/** The picture of a word: an emoji, or the learner's own photo (with the address of the full picture and of a small copy). */
export type Picture = Schemas["PictureOut"];
export type WordPage = Schemas["WordPage"];
export type UploadResult = Schemas["UploadResult"];
export type GlossResult = Schemas["GlossOut"];
export type GlossSpan = Schemas["GlossSpan"];
export type GlossWord = Schemas["GlossWord"];
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
export type Flashcard = Schemas["FlashcardOut"];
export type CardPreview = Schemas["Preview"];
export type ReviewResult = Schemas["ReviewResult"];
export type StudyStats = Schemas["StudyStats"];
export type HardWord = Schemas["HardWord"];
export type HardWords = Schemas["HardWords"];
/** 1 again, 2 hard, 3 good, 4 easy. */
export type Grade = 1 | 2 | 3 | 4;
export type PracticeMode = "flashcards" | "choices" | "dictation" | "pos" | "cloze";
export interface Review { word_id: number; grade: Grade; think_ms?: number; rate_ms?: number; mode?: PracticeMode; direction?: "word" | "meaning" }
/** What to practise in flashcards: every word, what is due now, or exactly these words. */
export type FlashcardScope = "all" | "due" | "ids";
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
export type Rewards = Schemas["RewardsOut"];
export type Badge = Schemas["BadgeOut"];
export type Records = Schemas["RecordsOut"];
export type Challenge = Schemas["ChallengeOut"];
export interface Answer { word_id: number; correct: boolean; think_ms?: number; mode?: PracticeMode; direction?: "word" | "meaning" }
export type ChoiceCard = Schemas["ChoiceOut"];
/** Which words to show or practise: every word, the General set, one set by id, or several at once as a comma list ("3,7,general"). */
export type SetFilter = "all" | "general" | number | string;
export interface DefineResult { defined: number; failed: number; remaining: number }
