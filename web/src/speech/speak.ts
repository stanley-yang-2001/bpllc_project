/** Read aloud with the browser's own speech engine (window.speechSynthesis). Nothing is sent to our server or to the AI model:
 * the text stays on the learner's device. Which voices exist depends on the device, so a missing voice is reported, not hidden. */

/** The site's language codes to the BCP 47 tag the browser's voices use. */
export const SPEECH_LANG: Record<string, string> = {
  en: "en-US", es: "es-ES", fr: "fr-FR", de: "de-DE", it: "it-IT", pt: "pt-BR", ja: "ja-JP", zh: "zh-CN", ko: "ko-KR",
};
export const SLOW_RATE = 0.6;
export const NORMAL_RATE = 0.9;
const CHUNK_MAX = 180;          // long utterances get cut off by some browsers, so a story is read a sentence group at a time

export const speechSupported = (): boolean =>
  typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";

/** Lines first, then sentences, then packed up to CHUNK_MAX characters. Chinese, Japanese and Korean full stops count. */
export function chunks(text: string): string[] {
  const out: string[] = [];
  for (const line of text.split(/\n+/)) {
    const clean = line.trim();
    if (!clean) continue;
    const parts = clean.match(/[^.!?。！？]+[.!?。！？]*\s*/g) ?? [clean];
    let cur = "";
    for (const part of parts) {
      if (cur && (cur + part).length > CHUNK_MAX) { out.push(cur.trim()); cur = ""; }
      cur += part;
      while (cur.length > CHUNK_MAX * 2) { out.push(cur.slice(0, CHUNK_MAX * 2)); cur = cur.slice(CHUNK_MAX * 2); }
    }
    if (cur.trim()) out.push(cur.trim());
  }
  return out;
}

const VOICE_KEY = "tutor.voice.";       // + language code: the voice the learner picked on THIS device (voices differ per device)

/** The voice name the learner picked for a language on this device, or "" for automatic. Never throws (storage can be blocked). */
export function chosenVoiceName(language: string): string {
  try { return window.localStorage.getItem(VOICE_KEY + language) ?? ""; } catch { return ""; }
}
export function chooseVoice(language: string, name: string): void {
  try { if (name) window.localStorage.setItem(VOICE_KEY + language, name); else window.localStorage.removeItem(VOICE_KEY + language); } catch { /* storage blocked: the choice just does not stick */ }
}

const norm = (lang: string) => lang.toLowerCase().replace("_", "-");

/** Every voice on the device that can read this language (Mandarin never gets a Cantonese voice), best first: the exact region, then
 * the natural/neural voices browsers such as Edge offer, then voices that work offline. */
export function voicesFor(language: string, all: SpeechSynthesisVoice[] = speechSupported() ? window.speechSynthesis.getVoices() : []): SpeechSynthesisVoice[] {
  const tag = (SPEECH_LANG[language] ?? language).toLowerCase();
  const prefix = tag.split("-")[0];
  const fits = (v: SpeechSynthesisVoice) => {
    const l = norm(v.lang);
    if (l !== prefix && !l.startsWith(prefix + "-")) return false;
    return !(prefix === "zh" && (l === "zh-hk" || /cantonese|yue/i.test(v.name)));
  };
  const score = (v: SpeechSynthesisVoice) => (norm(v.lang) === tag ? 8 : 0) + (/natural|neural|online/i.test(v.name) ? 4 : 0) + (v.localService ? 2 : 0) + (v.default ? 1 : 0);
  return all.filter(fits).sort((x, y) => score(y) - score(x));
}

/** The voice to use: the one the learner picked, else the best match. null = the device lists voices but none fit this language;
 * undefined = the device has not loaded its voice list yet (Chrome loads it late). */
export function voiceFor(language: string): SpeechSynthesisVoice | null | undefined {
  if (!speechSupported()) return null;
  const all = window.speechSynthesis.getVoices();
  if (all.length === 0) return undefined;
  const fit = voicesFor(language, all);
  const wanted = chosenVoiceName(language);
  return fit.find((v) => v.name === wanted) ?? fit[0] ?? null;
}

/** Resolves once the device's voice list is there (or after `ms`, so a device with no voices cannot hang a reading). */
export function whenVoicesLoaded(ms = 1500): Promise<void> {
  if (!speechSupported() || window.speechSynthesis.getVoices().length > 0) return Promise.resolve();
  const synth = window.speechSynthesis;
  return new Promise((resolve) => {
    const done = () => { clearTimeout(timer); synth.removeEventListener?.("voiceschanged", done); resolve(); };
    const timer = setTimeout(done, ms);
    synth.addEventListener?.("voiceschanged", done);
  });
}

/** A short greeting in each language, for trying a voice out. */
export const SAMPLE_TEXT: Record<string, string> = {
  en: "Hello, how are you?", es: "Hola, ¿cómo estás?", fr: "Bonjour, comment allez-vous ?", de: "Hallo, wie geht es dir?", it: "Ciao, come stai?",
  pt: "Olá, tudo bem?", ja: "こんにちは、お元気ですか？", zh: "你好，你好吗？", ko: "안녕하세요, 잘 지내세요?",
};

export interface SpeakHandlers { onEnd?: () => void; onError?: () => void; onNoVoice?: () => void }

/** Speaks `text` in `language`. Stops anything already being read. Returns a function that stops this reading. When the device has no
 * voice for the language nothing is read (a wrong-language voice would only mispronounce it) and `onNoVoice` is called instead. */
export function speak(text: string, language: string, rate: number, h: SpeakHandlers = {}): () => void {
  if (!speechSupported()) { h.onError?.(); return () => undefined; }
  const synth = window.speechSynthesis;
  synth.cancel();
  const queue = chunks(text);
  let stopped = false;
  const next = (voice: SpeechSynthesisVoice | null | undefined) => {
    if (stopped) return;
    const part = queue.shift();
    if (part === undefined) { h.onEnd?.(); return; }
    const u = new SpeechSynthesisUtterance(part);
    u.lang = voice?.lang ?? SPEECH_LANG[language] ?? language;
    u.rate = rate;
    if (voice) u.voice = voice;
    u.onend = () => next(voice);
    u.onerror = (e) => { if (stopped || (e as SpeechSynthesisErrorEvent).error === "canceled" || (e as SpeechSynthesisErrorEvent).error === "interrupted") return; stopped = true; h.onError?.(); };
    synth.speak(u);
  };
  if (queue.length === 0) { h.onEnd?.(); return () => undefined; }
  const begin = () => {
    if (stopped) return;
    const voice = voiceFor(language);
    if (voice === null) { stopped = true; h.onNoVoice?.(); return; }
    next(voice);
  };
  if (voiceFor(language) === undefined) void whenVoicesLoaded().then(begin); else begin();
  return () => { stopped = true; synth.cancel(); };
}
