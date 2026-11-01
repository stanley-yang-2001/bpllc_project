import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ActiveLanguageProvider } from "../auth/ActiveLanguage";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n/I18nProvider";
import { PreferencesProvider } from "../prefs/PreferencesProvider";
import { ALICE, mockApi } from "../test/helpers";
import { defineLoop } from "./defineLoop";
import { Pager } from "../components/Pager";
import { Toolbar } from "./Toolbar";
import { UploadNotice } from "./UploadNotice";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

function wrap(ui: ReactNode) {
  mockApi({ "GET /me": ALICE });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider><PreferencesProvider><ActiveLanguageProvider><I18nProvider>{ui}</I18nProvider></ActiveLanguageProvider></PreferencesProvider></AuthProvider>
    </QueryClientProvider>,
  );
}

describe("defineLoop", () => {
  it("asks again until nothing is left, and reports the running total", async () => {
    const answers = [{ defined: 25, failed: 0, remaining: 10 }, { defined: 10, failed: 1, remaining: 0 }];
    const { calls } = mockApi({ "POST /words/define": () => ({ json: answers.shift() }) });
    const seen: [number, number][] = [];
    const r = await defineLoop({ language: "en", set: "all" }, (done, left) => seen.push([done, left]));
    expect(r).toEqual({ done: 35, failed: 1, remaining: 0 });
    expect(seen).toEqual([[25, 10], [35, 0]]);
    expect(calls.filter((c) => c.path === "/words/define")).toHaveLength(2);
  });

  it("stops when a request writes nothing, so it cannot loop for ever", async () => {
    const { calls } = mockApi({ "POST /words/define": { defined: 0, failed: 3, remaining: 3 } });
    const r = await defineLoop({ language: "en" }, () => undefined);
    expect(r).toEqual({ done: 0, failed: 3, remaining: 3 });
    expect(calls.filter((c) => c.path === "/words/define")).toHaveLength(1);
  });
});

describe("Pager", () => {
  it("shows nothing when everything fits on one page", () => {
    wrap(<Pager offset={0} limit={50} total={50} onOffset={() => undefined} />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("moves by one page in each direction and disables the ends", async () => {
    const go = vi.fn();
    wrap(<Pager offset={50} limit={50} total={120} onOffset={go} />);
    await userEvent.click(screen.getByRole("button", { name: /Previous/ }));
    await userEvent.click(screen.getByRole("button", { name: /Next/ }));
    expect(go.mock.calls).toEqual([[0], [100]]);
  });

  it("cannot go back from the first page or on from the last", () => {
    const { unmount } = wrap(<Pager offset={0} limit={50} total={120} onOffset={() => undefined} />);
    expect(screen.getByRole("button", { name: /Previous/ })).toBeDisabled();
    unmount();
    wrap(<Pager offset={100} limit={50} total={120} onOffset={() => undefined} />);
    expect(screen.getByRole("button", { name: /Next/ })).toBeDisabled();
  });
});

describe("UploadNotice", () => {
  it("lists each rejected row with its reason", () => {
    wrap(<UploadNotice result={{ added: 2, duplicates: 1, invalid_count: 1, invalid: [{ row: 4, reason: "empty word" }] }} />);
    expect(screen.getByRole("status")).toHaveTextContent("empty word");
  });
});

describe("Toolbar", () => {
  const props = { search: "", onSearch: () => undefined, showReading: false, readingLoading: false, onToggleReading: () => undefined,
    defining: false, onDefine: () => undefined, labelling: false, onLabel: () => undefined, uploading: false, onCsv: () => undefined };

  it("has every tool, and the five buttons share one size", async () => {
    wrap(<Toolbar {...props} />);
    const names = ["Show pronunciation", "Upload CSV", "Write missing meanings", "Label parts of speech"];
    for (const name of names) expect(screen.getByRole("button", { name })).toHaveClass("sm:w-56");
    expect(screen.getByLabelText("Search words")).toBeInTheDocument();
    expect(await screen.findByLabelText(/Write meanings in/)).toBeInTheDocument();
  });

  it("hands a chosen CSV file up and runs the tutor's tools", async () => {
    const onCsv = vi.fn(), onDefine = vi.fn(), onLabel = vi.fn();
    wrap(<Toolbar {...props} onCsv={onCsv} onDefine={onDefine} onLabel={onLabel} />);
    await userEvent.click(screen.getByRole("button", { name: "Write missing meanings" }));
    await userEvent.click(screen.getByRole("button", { name: "Label parts of speech" }));
    const file = new File(["word,meaning\nhi,hello"], "words.csv", { type: "text/csv" });
    await userEvent.upload(screen.getByLabelText(/CSV file/i), file);
    expect(onDefine).toHaveBeenCalledOnce();
    expect(onLabel).toHaveBeenCalledOnce();
    expect(onCsv).toHaveBeenCalledWith(file);
  });
});
