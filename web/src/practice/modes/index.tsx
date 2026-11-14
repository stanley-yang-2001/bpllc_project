import { CardsMode } from "./cards";
import { ChoiceMode } from "./choice";
import { ClozeMode } from "./cloze";
import { DictationMode } from "./dictation";
import { PosMode } from "./pos";
import type { Launch, ModeId, PracticeContext, PracticeMode } from "./types";

/** Every practice mode, in the order of the menu. The Practice page only loops over this, so a new mode is one file and one line here. */
export const MODES: { [M in ModeId]: PracticeMode<M> } = { choice: ChoiceMode, cards: CardsMode, pos: PosMode, dictation: DictationMode, cloze: ClozeMode };
export const MODE_ORDER = Object.keys(MODES) as ModeId[];

/** Runs the session for a launch: finds the mode and hands it its own kind of launch. */
export function ModeSession({ launch, ctx, onDone, start }: { launch: Launch; ctx: PracticeContext; onDone: () => void; start: (l: Launch) => void }) {
  const { Session } = MODES[launch.mode] as unknown as PracticeMode;      // the one place the launch's kind is trusted to match its mode
  return <Session ctx={ctx} launch={launch} onDone={onDone} start={start} />;
}

/** The menu card of one mode. */
export function ModeTileFor({ id, ctx, start }: { id: ModeId; ctx: PracticeContext; start: (l: Launch) => void }) {
  const { Tile } = MODES[id] as unknown as PracticeMode;
  return <Tile ctx={ctx} start={start} />;
}
export type { Launch, ModeId, PracticeContext } from "./types";
