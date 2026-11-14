import { act, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const record = vi.fn();
vi.mock("./useRecorder", () => ({ useAnswerRecorder: () => ({ record, failed: false }), useThinkTimer: () => () => 1234 }));
vi.mock("../i18n/I18nProvider", () => ({ useI18n: () => ({ t: (k: string) => k }) }));

import { QuizFeedback, QuizScore, useQuizRound } from "./quiz";

describe("useQuizRound", () => {
  it("counts a right answer once and ignores a second pick of the same question", () => {
    record.mockClear();
    const { result } = renderHook(() => useQuizRound("es", true));
    act(() => result.current.choose("agua", 7, true, { mode: "choices", direction: "word" }));
    act(() => result.current.choose("fuego", 7, false, { mode: "choices", direction: "word" }));
    expect(record).toHaveBeenCalledTimes(1);
    expect(record).toHaveBeenCalledWith(7, true, { think_ms: 1234, mode: "choices", direction: "word" });
    expect(result.current.picked).toBe("agua");
    expect(result.current.right).toBe(1);
  });

  it("moves on, and starts over with a clean score", () => {
    const { result } = renderHook(() => useQuizRound("es", true));
    act(() => result.current.choose("a", 1, true, { mode: "pos" }));
    act(() => result.current.next());
    expect(result.current).toMatchObject({ index: 1, picked: null, right: 1 });
    act(() => result.current.restart());
    expect(result.current).toMatchObject({ index: 0, picked: null, right: 0 });
  });

  it("a typed answer is graded without a picked option", () => {
    record.mockClear();
    const { result } = renderHook(() => useQuizRound("es", true));
    act(() => result.current.grade(3, false, { mode: "dictation" }));
    expect(record).toHaveBeenCalledWith(3, false, { think_ms: 1234, mode: "dictation" });
    expect(result.current).toMatchObject({ right: 0, picked: null });
  });
});

describe("quiz screens", () => {
  it("the feedback offers the result on the last question, else Next", async () => {
    const next = vi.fn();
    const { rerender } = render(<QuizFeedback correct message="Right!" last={false} onNext={next}><span>extra</span></QuizFeedback>);
    expect(screen.getByText("Right!")).toHaveClass("text-emerald-700");
    expect(screen.getByText("extra")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "common.next" }));
    expect(next).toHaveBeenCalled();
    rerender(<QuizFeedback correct={false} message="No" last onNext={next} />);
    expect(screen.getByText("No")).toHaveClass("text-red-700");
    expect(screen.getByRole("button", { name: "practice.cloze.seeResult" })).toBeInTheDocument();
  });

  it("the score screen shows the title, the save warning and both buttons", async () => {
    const again = vi.fn(), done = vi.fn();
    render(<QuizScore title="3 of 4" againLabel="Again" failed onAgain={again} onDone={done} />);
    expect(screen.getByText("3 of 4")).toBeInTheDocument();
    expect(screen.getByText("practice.saveFailed")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Again" }));
    await userEvent.click(screen.getByRole("button", { name: "common.back" }));
    expect(again).toHaveBeenCalled(); expect(done).toHaveBeenCalled();
  });
});
