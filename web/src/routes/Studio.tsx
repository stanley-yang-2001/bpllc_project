import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus, GraduationCap, RefreshCw, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type DifficultyChoice, type GeneratedStory } from "../api/client";
import { storiesKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { StoryReport } from "../components/StoryReport";
import { StoryTools } from "../text/StoryTools";
import { diffLabel, topicLabel, typeLabel } from "../i18n/labels";
import { useI18n } from "../i18n/I18nProvider";
import { nothingTicked, SetPicker, setIdsToSend, type SetChoice } from "../components/SetPicker";
import { Badge, Button, Card, ErrorText, inputCls, Notice, PageHeader } from "../components/ui";

const CLASSIC = ["narration", "dialogue"];          // these two have no topic
const CUSTOM = "__custom__";                        // the "Write my own…" choice; never sent to the API
const CUSTOM_TOPIC = "__custom_topic__";            // the same for the topic
const CUSTOM_MAX = 40;
const PRESETS = { easy: { length: 60, own_words: 3, uncommon_pct: 5 }, medium: { length: 110, own_words: 5, uncommon_pct: 10 }, hard: { length: 200, own_words: 8, uncommon_pct: 20 } } as const;
const LIMITS = { length: [20, 400], own_words: [1, 30], uncommon_pct: [0, 50] } as const;       // the API checks the same limits
type Tier = "" | "easy" | "medium" | "hard" | "custom";
const ownModelName = (report: unknown): string | null => {
  const m = (report as { model?: { custom?: boolean; name?: string } } | undefined)?.model;
  return m?.custom ? m.name ?? null : null;
};

const whole = (text: string, [lo, hi]: readonly [number, number]): number | null => {
  const n = Number(text);
  return text.trim() !== "" && Number.isInteger(n) && n >= lo && n <= hi ? n : null;
};

/** The same rule the API applies (tutor_core.prompts.clean_free_text), so a bad label is explained here and Make stays off.
 * The API is the authority and checks again. */
export function customLabel(text: string): string | null {
  const clean = text.trim().replace(/\s+/g, " ");
  const ok = clean.length > 0 && clean.length <= CUSTOM_MAX && clean.split(" ").length <= 6
    && /^[\p{L}\p{M}\p{N}'\u2019 -]+$/u.test(clean) && /[\p{L}\p{N}]/u.test(clean);
  return ok ? clean : null;
}

/** The tier a generated story was made with, read back from its report so Save records the same one. */
function requestedOf(report: GeneratedStory["report"]): DifficultyChoice {
  const r = (report as { difficulty?: { requested?: { tier?: string; length?: number; own_words?: number; uncommon_pct?: number } } }).difficulty?.requested;
  if (!r?.tier) return {};
  return r.tier === "custom" ? { difficulty: "custom", length: r.length, own_words: r.own_words, uncommon_pct: r.uncommon_pct } : { difficulty: r.tier };
}

export default function Studio() {
  const { active, info } = useActiveLanguage();
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const { t, err } = useI18n();
  const lang = info(active);
  const name = lang?.native ?? active;
  const options = useQuery({ queryKey: ["story-options"], queryFn: api.storyOptions, staleTime: Infinity });
  const [type, setType] = useState("");
  const [topic, setTopic] = useState("");
  const [custom, setCustom] = useState("");
  const [customTopic, setCustomTopic] = useState("");
  const [tier, setTier] = useState<Tier>("");
  const [nums, setNums] = useState({ length: "110", own_words: "5", uncommon_pct: "10" });
  const [sets, setSets] = useState<SetChoice>(null);       // null = every set (General always among them)
  const [story, setStory] = useState<GeneratedStory | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);
  const saved = savedId !== null;
  const generate = useMutation({ mutationFn: api.generateStory, onSuccess: (s) => { setStory(s); setSavedId(null); } });
  const save = useMutation({
    mutationFn: api.saveStory,
    onSuccess: (s) => {
      setSavedId(s.id);
      toast(t("common.savedToLibrary"));
      if (user) void qc.invalidateQueries({ queryKey: storiesKey(user.id) });
    },
  });

  useEffect(() => { setSets(null); setStory(null); setSavedId(null); generate.reset(); save.reset(); }, [active]);   // a story belongs to one language

  const kind = type === CUSTOM ? customLabel(custom) ?? "" : type;       // "" = surprise me (or an unusable label, which blocks Make)
  const customBad = type === CUSTOM && !kind;
  const topicValue = topic === CUSTOM_TOPIC ? customLabel(customTopic) ?? "" : topic;    // same rule and limits as a custom kind
  const topicOn = !!kind && !CLASSIC.includes(kind);
  const topicBad = topicOn && topic === CUSTOM_TOPIC && !topicValue;
  const picked = { length: whole(nums.length, LIMITS.length), own_words: whole(nums.own_words, LIMITS.own_words), uncommon_pct: whole(nums.uncommon_pct, LIMITS.uncommon_pct) };
  const diffBad = tier === "custom" && (picked.length === null || picked.own_words === null || picked.uncommon_pct === null);
  const choice: DifficultyChoice = tier === "" ? {} : tier === "custom"
    ? { difficulty: "custom", length: picked.length ?? undefined, own_words: picked.own_words ?? undefined, uncommon_pct: picked.uncommon_pct ?? undefined }
    : { difficulty: tier };
  const make = () => generate.mutate({ language: active, story_type: kind || undefined, topic: !topicOn ? undefined : topicValue || undefined, ...choice, ...(setIdsToSend(sets) ? { set_ids: setIdsToSend(sets) } : {}) });
  const enabled = lang?.stories_enabled !== false;
  const failure = generate.error instanceof ApiError ? generate.error : null;

  return (
    <div>
      <PageHeader
        title={t("studio.title")}
        description={t("studio.description")}
        actions={<Badge tone="brand"><span lang={active}>{name}</span></Badge>}
      />
      <Card className="space-y-4">
        {!enabled ? (
          <Notice tone="warning">{t("studio.unavailable", { language: name })}</Notice>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="story-type" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.kind")}</label>
                <select id="story-type" className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
                  <option value="">{t("studio.surprise")}</option>
                  {options.data?.types.map((ty) => <option key={ty} value={ty}>{typeLabel(t, ty)}</option>)}
                  <option value={CUSTOM}>{t("studio.kindCustom")}</option>
                </select>
                {type === CUSTOM && (
                  <div className="mt-2">
                    <label htmlFor="story-custom" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.customLabel")}</label>
                    <input
                      id="story-custom" className={inputCls} value={custom} maxLength={CUSTOM_MAX} lang={active}
                      onChange={(e) => setCustom(e.target.value)} aria-describedby="story-custom-hint"
                      aria-invalid={custom.trim() !== "" && customBad}
                    />
                    <p id="story-custom-hint" className={`mt-1 text-xs ${custom.trim() !== "" && customBad ? "text-red-700" : "text-slate-600"}`}>{t("studio.customHint")}</p>
                  </div>
                )}
              </div>
              <div>
                <label htmlFor="story-topic" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.topic")}</label>
                <select id="story-topic" className={inputCls} value={topic} onChange={(e) => setTopic(e.target.value)} disabled={!kind || CLASSIC.includes(kind)}>
                  <option value="">{t("studio.anyTopic")}</option>
                  {options.data?.topics.map((tp) => <option key={tp} value={tp}>{topicLabel(t, tp)}</option>)}
                  <option value={CUSTOM_TOPIC}>{t("studio.kindCustom")}</option>
                </select>
                {topicOn && topic === CUSTOM_TOPIC && (
                  <div className="mt-2">
                    <label htmlFor="story-topic-custom" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.topicCustomLabel")}</label>
                    <input
                      id="story-topic-custom" className={inputCls} value={customTopic} maxLength={CUSTOM_MAX} lang={active}
                      onChange={(e) => setCustomTopic(e.target.value)} aria-describedby="story-topic-custom-hint"
                      aria-invalid={customTopic.trim() !== "" && topicBad}
                    />
                    <p id="story-topic-custom-hint" className={`mt-1 text-xs ${customTopic.trim() !== "" && topicBad ? "text-red-700" : "text-slate-600"}`}>{t("studio.topicCustomHint")}</p>
                  </div>
                )}
                {(!kind || CLASSIC.includes(kind)) && <p className="mt-1 text-xs text-slate-600">{t("studio.topicHint")}</p>}
              </div>
            </div>
            <div>
              <label htmlFor="story-difficulty" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.difficulty")}</label>
              <select id="story-difficulty" className={`${inputCls} sm:max-w-xs`} value={tier} onChange={(e) => setTier(e.target.value as Tier)}>
                <option value="">{t("studio.diffAny")}</option>
                <option value="easy">{t("studio.diffEasy")}</option>
                <option value="medium">{t("studio.diffMedium")}</option>
                <option value="hard">{t("studio.diffHard")}</option>
                <option value="custom">{t("studio.diffCustom")}</option>
              </select>
              {tier !== "" && tier !== "custom" && (
                <p className="mt-1 text-xs text-slate-600">{t("studio.diffPreset", { length: PRESETS[tier].length, own: PRESETS[tier].own_words, pct: PRESETS[tier].uncommon_pct })}</p>
              )}
              {tier === "custom" && (
                <div className="mt-2 grid gap-3 sm:grid-cols-3">
                  {([["length", "studio.diffLength"], ["own_words", "studio.diffOwn"], ["uncommon_pct", "studio.diffUncommon"]] as const).map(([key, label]) => (
                    <div key={key}>
                      <label htmlFor={`diff-${key}`} className="mb-1 block text-sm font-medium text-slate-700">{t(label)}</label>
                      <input
                        id={`diff-${key}`} type="number" inputMode="numeric" className={inputCls} value={nums[key]}
                        min={LIMITS[key][0]} max={LIMITS[key][1]} step={1}
                        onChange={(e) => setNums({ ...nums, [key]: e.target.value })}
                        aria-invalid={picked[key] === null}
                      />
                    </div>
                  ))}
                  <p className={`text-xs sm:col-span-3 ${diffBad ? "text-red-700" : "text-slate-600"}`}>
                    {diffBad && <>{t("studio.diffBad")} </>}
                    {t("studio.diffLimits", { lmin: LIMITS.length[0], lmax: LIMITS.length[1], omin: LIMITS.own_words[0], omax: LIMITS.own_words[1], umin: LIMITS.uncommon_pct[0], umax: LIMITS.uncommon_pct[1] })}
                  </p>
                </div>
              )}
              {tier !== "" && <p className="mt-1 text-xs text-slate-600">{t("studio.diffNote")}</p>}
            </div>
            <SetPicker language={active} value={sets} onChange={setSets} idPrefix="studio-set" />
            <div>
              <Button onClick={make} loading={generate.isPending} disabled={customBad || topicBad || diffBad || nothingTicked(sets)} icon={<Sparkles aria-hidden className="size-4" />}>
                {generate.isPending ? t("studio.writing") : t("studio.make")}
              </Button>
              {generate.isPending && <p role="status" className="mt-2 text-sm text-slate-600">{t("studio.wait")}</p>}
              {failure && (
                <ErrorText>
                  {err(failure)}
                  {failure.code === "not_enough_words" && <> <Link to="/vocabulary" className="font-medium underline">{t("studio.goVocab")}</Link>.</>}
                </ErrorText>
              )}
              {generate.error && !failure && <ErrorText>{err(generate.error)}</ErrorText>}
            </div>
          </>
        )}
      </Card>

      {story && (
        <Card className="mt-4 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{typeLabel(t, story.story_type ?? "story")}</Badge>
            {story.topic && <Badge>{topicLabel(t, story.topic)}</Badge>}
            {requestedOf(story.report).difficulty && <Badge>{diffLabel(t, requestedOf(story.report).difficulty!)}</Badge>}
            <span className="text-xs text-slate-600">{t("studio.builtFrom", { used: story.words_used, total: story.words_total })}</span>
          </div>
          <p lang={story.language} className="whitespace-pre-wrap break-words text-base leading-relaxed text-slate-900">{story.story}</p>
          <StoryTools text={story.story} language={story.language} id="studio" />
          <StoryReport report={story.report} languageName={name} />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => save.mutate({ language: story.language, body: story.story, story_type: story.story_type, topic: story.topic, ...requestedOf(story.report), ...(ownModelName(story.report) ? { model: ownModelName(story.report) } : {}) })}
              disabled={saved}
              loading={save.isPending}
              icon={<BookmarkPlus aria-hidden className="size-4" />}
            >
              {saved ? t("chat.saved") : t("studio.save")}
            </Button>
            {saved && (
              <Link to={`/practice?story=${savedId}`} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-surface px-3.5 py-2 text-sm font-medium text-slate-700 shadow-xs hover:bg-slate-100/70">
                <GraduationCap aria-hidden className="size-4" />{t("studio.practice")}
              </Link>
            )}
            <Button variant="ghost" onClick={make} disabled={generate.isPending} icon={<RefreshCw aria-hidden className="size-4" />}>{t("studio.another")}</Button>
          </div>
          {save.error && <ErrorText>{err(save.error, "common.saveFailed")}</ErrorText>}
        </Card>
      )}
    </div>
  );
}
