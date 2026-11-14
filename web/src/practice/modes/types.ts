import type { ComponentType } from "react";
import type { FlashcardScope, PracticeProgress, SetFilter } from "../../api/types";
import type { Direction } from "../Choices";

/** One way to start a practice session, with whatever that mode needs. Add a mode = add a member here, one file in this folder and
 * one line in index.tsx; the Practice page itself does not change. */
export type Launch =
  | { mode: "choice"; direction: Direction }
  | { mode: "cards"; scope: FlashcardScope; ids: number[] }
  | { mode: "pos" }
  | { mode: "dictation" }
  | { mode: "cloze"; storyId: number };
export type ModeId = Launch["mode"];
export type LaunchOf<M extends ModeId> = Extract<Launch, { mode: M }>;

/** What the Practice page knows and every mode may use: the language being studied, the chosen word sets, the "due only" tick. */
export interface PracticeContext {
  language: string; name: string; set: SetFilter; dueOnly: boolean; progress: PracticeProgress | undefined;
}

export interface PracticeMode<M extends ModeId = ModeId> {
  /** The card on the practice menu. Calls `start` to begin a session. */
  Tile: ComponentType<{ ctx: PracticeContext; start: (launch: LaunchOf<M>) => void }>;
  /** The session itself. `start` lets it begin another one (e.g. flashcards: "practise the missed words"). */
  Session: ComponentType<{ ctx: PracticeContext; launch: LaunchOf<M>; onDone: () => void; start: (launch: Launch) => void }>;
}
