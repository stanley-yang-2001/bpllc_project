import { useEffect, useRef } from "react";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { useToast } from "../components/Toast";
import { badgeText } from "./badgeText";
import { useCelebrate } from "./Celebration";
import { badgeLevel, GOAL_LEVEL } from "./effects";
import { recordLabel } from "./RecordsCard";
import { beaten, remember, type Seen } from "./records";
import { useRewards } from "./useRewards";

const seenKey = (userId: number) => `tutor:badges-seen:${userId}`;
const recordsKey = (userId: number) => `tutor:records-seen:${userId}`;
const today = () => new Date().toISOString().slice(0, 10);

/** Says "New badge: ..." once for each badge earned since this browser last looked. The first time on a device it only records what is earned
 * (no flood of toasts for old badges). The list of seen badges is only a convenience of this browser; losing it costs one repeated toast. */
export function NewBadgeToasts() {
  const { user } = useAuth();
  const { t } = useI18n();
  const toast = useToast();
  const { data } = useRewards();
  const celebrate = useCelebrate();
  const wasReached = useRef<boolean | null>(null);
  const wasBack = useRef<boolean | null>(null);
  const challengeDone = useRef<{ id: string; done: boolean } | null>(null);
  useEffect(() => {
    if (!data || !data.show_rewards || !user) return;
    const earned = data.badges.filter((b) => b.earned);
    let seen: string[] | null = null;
    try { const raw = localStorage.getItem(seenKey(user.id)); seen = raw ? (JSON.parse(raw) as string[]) : null; } catch { /* storage blocked */ }
    const fresh = seen === null ? [] : earned.filter((b) => !seen!.includes(b.id));
    fresh.slice(0, 2).forEach((b) => toast(t("rewards.badge.new", { name: badgeText(b.id, b.target, t).name })));
    const top = fresh.reduce<typeof fresh[number] | null>((m, b) => (m === null || badgeLevel(b.id) > badgeLevel(m.id) ? b : m), null);
    if (top) celebrate(badgeLevel(top.id), t("rewards.badge.new", { name: badgeText(top.id, top.target, t).name }));
    // the daily goal: only on the step from "not yet" to "reached" while this page is open (never when the page loads already reached)
    if (wasReached.current === false && data.goal.reached) celebrate(GOAL_LEVEL, t("rewards.fx.goal"));
    wasReached.current = data.goal.reached;
    // the weekly challenge: only on the step from "not yet" to "done" for the same challenge while this page is open
    const ch = data.challenge, last = challengeDone.current;
    if (last && last.id === ch.id && !last.done && ch.done) {
      toast(t("rewards.fx.challenge"));
      celebrate(4, t("rewards.fx.challenge"));
    }
    challengeDone.current = { id: ch.id, done: ch.done };
    // coming back after a break: the first answers of the day get a welcome
    const back = data.comeback ? data.comeback.returned : null;
    if (wasBack.current === false && back === true) celebrate(2, t("rewards.fx.back"));
    wasBack.current = back;
    // personal records: said once per kind per day (a record day beats itself with every answer), and never for a first-ever value
    try {
      const raw = localStorage.getItem(recordsKey(user.id));
      const stored = raw ? (JSON.parse(raw) as { seen: Seen; told: Record<string, string> }) : null;
      const told = stored?.told ?? {};
      if (stored) {
        const fresh = beaten(stored.seen, data.records).filter((k) => told[k] !== today());
        if (fresh.length) {
          const name = t(recordLabel(fresh[0]));
          toast(t("rewards.records.new", { name }));
          celebrate(3, t("rewards.records.new", { name }));
          fresh.forEach((k) => { told[k] = today(); });
        }
      }
      localStorage.setItem(recordsKey(user.id), JSON.stringify({ seen: remember(stored?.seen ?? {}, data.records), told }));
    } catch { /* storage blocked */ }
    try { localStorage.setItem(seenKey(user.id), JSON.stringify(earned.map((b) => b.id))); } catch { /* storage blocked */ }
  }, [data, user, t, toast, celebrate]);
  return null;
}
