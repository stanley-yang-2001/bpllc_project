import type { GlossSpan } from "../api/client";

/** One stretch of a story. `start` and `end` index the story text (JavaScript string indices, the ones the API sends).
 * text: spaces, punctuation, and nothing to tap; known: one of the learner's words; other: a word of the story that is not in their list. */
export type Segment =
  | { kind: "text"; text: string; start: number; end: number }
  | { kind: "known"; text: string; start: number; end: number; wordId: number }
  | { kind: "other"; text: string; start: number; end: number };

const cache = new Map<string, Intl.Segmenter | null>();

/** The browser's own word splitter (it knows where a Chinese or Japanese word ends); null where the browser has none. */
function splitter(language: string): Intl.Segmenter | null {
  if (!cache.has(language)) {
    try {
      cache.set(language, typeof Intl !== "undefined" && "Segmenter" in Intl ? new Intl.Segmenter(language, { granularity: "word" }) : null);
    } catch {
      cache.set(language, null);
    }
  }
  return cache.get(language) ?? null;
}

const WORD = /[\p{L}\p{M}]+(?:['’-][\p{L}\p{M}]+)*/gu;
const HAS_LETTER = /\p{L}/u;

/** The words of a plain stretch with their places in it (numbers and punctuation are not words). */
function wordsOf(text: string, language: string): { start: number; end: number }[] {
  const seg = splitter(language);
  if (seg) {
    return [...seg.segment(text)].filter((s) => s.isWordLike && HAS_LETTER.test(s.segment)).map((s) => ({ start: s.index, end: s.index + s.segment.length }));
  }
  return [...text.matchAll(WORD)].map((m) => ({ start: m.index, end: m.index + m[0].length }));
}

/** The story cut into pieces: the learner's words (from the API's spans), the other words, and what lies between. Joined again, the pieces are the text. */
export function segments(text: string, spans: GlossSpan[], language: string): Segment[] {
  const out: Segment[] = [];
  const plain = (from: number, to: number) => {
    if (to <= from) return;
    const chunk = text.slice(from, to);
    let at = 0;
    for (const w of wordsOf(chunk, language)) {
      if (w.start > at) out.push({ kind: "text", text: chunk.slice(at, w.start), start: from + at, end: from + w.start });
      out.push({ kind: "other", text: chunk.slice(w.start, w.end), start: from + w.start, end: from + w.end });
      at = w.end;
    }
    if (at < chunk.length) out.push({ kind: "text", text: chunk.slice(at), start: from + at, end: to });
  };
  let at = 0;
  for (const s of [...spans].sort((a, b) => a.start - b.start)) {
    if (s.start < at || s.end <= s.start || s.end > text.length) continue;          // the API never sends one that overlaps or leaves the text; skipped rather than trusted
    plain(at, s.start);
    out.push({ kind: "known", text: text.slice(s.start, s.end), start: s.start, end: s.end, wordId: s.word_id });
    at = s.end;
  }
  plain(at, text.length);
  return out;
}

/** The form to add to the list for a tapped word: as written, except that a capital that is only there because the word starts a sentence
 * (or a line, or follows a speaker's colon) is lowered. German keeps its capitals: every noun has one. */
export function learnable(text: string, start: number, end: number, language: string): string {
  const word = text.slice(start, end);
  if (language === "de" || word.length < 2) return word;
  const before = text.slice(0, start).replace(/[\s"'“”‘’«»(¿¡]+$/u, "");
  const startsSentence = before === "" || /[.!?…:：。！？\n]$/u.test(before) || /\n\s*$/u.test(text.slice(0, start));
  const onlyFirstCapital = word === word[0].toUpperCase() + word.slice(1).toLowerCase() && word !== word.toLowerCase();
  return startsSentence && onlyFirstCapital ? word.toLowerCase() : word;
}
