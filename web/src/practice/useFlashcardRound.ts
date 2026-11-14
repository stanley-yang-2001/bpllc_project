import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { rewardsKey } from "../api/keys";
import type { Flashcard, Grade } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { useCelebrate } from "../rewards/Celebration";
import { milestoneFor } from "../rewards/effects";
import { answered, startSession, take, type Session } from "./session";

/** Everything about one round of flashcards except how it looks: the queue (session.ts), the timer, revealing and grading (saved at
 * once with how long it took), the 1 to 4 keys, and the celebrations. `seconds` null = no time limit. */
export function useFlashcardRound({ language, cards, seconds }: { language: string; cards: Flashcard[]; seconds: number | null }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const qc = useQueryClient();
  const celebrate = useCelebrate();
  const [start] = useState(() => take(startSession(cards), Date.now()));
  const [session, setSession] = useState<Session>(start.session);
  const [card, setCard] = useState<Flashcard | null>(start.card);
  const [deadline] = useState(() => (seconds ? Date.now() + seconds * 1000 : null));
  const [now, setNow] = useState(() => Date.now());
  const [timeUp, setTimeUp] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  const shownAt = useRef(performance.now());              // the card appeared
  const revealedAt = useRef<number | null>(null);          // the learner checked the answer

  const reveal = useCallback(() => {
    if (revealed || !card) return;
    revealedAt.current = performance.now();
    setRevealed(true);
  }, [revealed, card]);

  const grade = useCallback((g: Grade) => {
    if (!card || !revealed || saving || revealedAt.current === null) return;
    const now = performance.now();
    const think = Math.round(revealedAt.current - shownAt.current);
    const rate = Math.round(now - revealedAt.current);
    setSaving(true);
    const finish = (result: Awaited<ReturnType<typeof api.recordReviews>>[number] | null) => {
      const moved = answered(session, card, g, result, Date.now(), think, rate);
      const next = take(moved, Date.now());
      const hit = milestoneFor(moved.log);                    // a run of answers or a card count worth a celebration
      if (hit) celebrate(hit.level, t(hit.kind === "combo" ? "rewards.fx.combo" : "rewards.fx.cards", { n: hit.n }));
      setSession(next.session);
      setCard(deadline !== null && Date.now() >= deadline ? null : next.card);
      setRevealed(false);
      revealedAt.current = null;
      shownAt.current = performance.now();
      setSaving(false);
      void qc.invalidateQueries({ queryKey: ["practice", user!.id, "progress"] });
      void qc.invalidateQueries({ queryKey: ["practice", user!.id, "stats"] });
      void qc.invalidateQueries({ queryKey: ["practice", user!.id, "hardest"] });
      void qc.invalidateQueries({ queryKey: rewardsKey(user!.id, language) });
    };
    api.recordReviews([{ word_id: card.id, grade: g, think_ms: think, rate_ms: rate, mode: "flashcards", direction: "word" }])
      .then((r) => finish(r[0]))
      .catch(() => { setFailed(true); finish(null); });
  }, [card, revealed, saving, session, qc, user, celebrate, t, language, deadline]);

  useEffect(() => {                                           // keys 1 to 4 grade the answer, same as the buttons
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      if (revealed && ["1", "2", "3", "4"].includes(e.key)) grade(Number(e.key) as Grade);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [revealed, grade]);

  useEffect(() => {
    if (deadline === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [deadline]);
  // when the time is up the card on screen is finished (so the answer being given is not lost), then the summary comes
  const over = deadline !== null && now >= deadline;
  useEffect(() => { if (over && !revealed && !saving) setTimeUp(true); }, [over, revealed, saving]);

  const finished = card === null || timeUp || (over && !revealed);
  return { session, card, revealed, saving, failed, deadline, now, over, finished, reveal, grade };
}
