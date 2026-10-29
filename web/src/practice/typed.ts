/** How a typed answer compares with the word: "right" ignores case, spacing and punctuation round the edges; "accents" means the
 * letters are right but an accent or mark is missing or wrong (that still counts as wrong, but the learner is told why). */
export type TypedResult = "right" | "accents" | "wrong";

const EDGE = /^[\s.,!?¡¿;:"'“”‘’«»()[\]{}…。！？、，；：「」『』（）]+|[\s.,!?¡¿;:"'“”‘’«»()[\]{}…。！？、，；：「」『』（）]+$/g;
const clean = (s: string) => s.normalize("NFC").replace(EDGE, "").replace(/\s+/g, " ").toLocaleLowerCase();
const bare = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").normalize("NFC");

export function checkTyped(typed: string, answer: string): TypedResult {
  const a = clean(typed), b = clean(answer);
  if (a === "") return "wrong";
  if (a === b) return "right";
  return bare(a) === bare(b) ? "accents" : "wrong";
}
