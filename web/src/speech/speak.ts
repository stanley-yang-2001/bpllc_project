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

/** A voice for the language, or null when the device lists voices but none match. `undefined` = voices not loaded yet. */
export function voiceFor(language: string): SpeechSynthesisVoice | null | undefined {
  if (!speechSupported()) return null;
  const voices = window.speechSynthesis.getVoices();
  if (voices.length === 0) return undefined;
  const tag = (SPEECH_LANG[language] ?? language).toLowerCase();
  const prefix = tag.split("-")[0];
  return voices.find((v) => v.lang.toLowerCase().replace("_", "-") === tag) ?? voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ?? null;
}

export interface SpeakHandlers { onEnd?: () => void; onError?: () => void }

/** Speaks `text` in `language`. Stops anything already being read. Returns a function that stops this reading. */
export function speak(text: string, language: string, rate: number, h: SpeakHandlers = {}): () => void {
  if (!speechSupported()) { h.onError?.(); return () => undefined; }
  const synth = window.speechSynthesis;
  synth.cancel();
  const queue = chunks(text);
  let stopped = false;
  const voice = voiceFor(language);
  const next = () => {
    if (stopped) return;
    const part = queue.shift();
    if (part === undefined) { h.onEnd?.(); return; }
    const u = new SpeechSynthesisUtterance(part);
    u.lang = SPEECH_LANG[language] ?? language;
    u.rate = rate;
    if (voice) u.voice = voice;
    u.onend = next;
    u.onerror = (e) => { if (stopped || (e as SpeechSynthesisErrorEvent).error === "canceled" || (e as SpeechSynthesisErrorEvent).error === "interrupted") return; stopped = true; h.onError?.(); };
    synth.speak(u);
  };
  if (queue.length === 0) { h.onEnd?.(); return () => undefined; }
  next();
  return () => { stopped = true; synth.cancel(); };
}
