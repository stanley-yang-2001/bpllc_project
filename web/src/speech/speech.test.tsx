import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { translate } from "../i18n/I18nProvider";
import { chunks, NORMAL_RATE, SLOW_RATE, speak, voiceFor } from "./speak";
import { SpeakButton } from "./SpeakButton";

vi.mock("../i18n/I18nProvider", async (orig) => ({
  ...(await orig<typeof import("../i18n/I18nProvider")>()),
  useI18n: () => ({ t: (k: string, p?: Record<string, string | number>) => translate("en", k as never, p) }),
}));

interface Spoken { text: string; lang: string; rate: number; voice: unknown; finish: () => void }
let spoken: Spoken[];
let cancelled: number;
let voices: { lang: string; name: string }[];

function installFakeSpeech() {
  spoken = []; cancelled = 0;
  class FakeUtterance {
    onend: (() => void) | null = null; onerror: ((e: unknown) => void) | null = null;
    lang = ""; rate = 1; voice: unknown = null;
    constructor(public text: string) {}
  }
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  const synth = {
    speak: (u: FakeUtterance) => spoken.push({ text: u.text, lang: u.lang, rate: u.rate, voice: u.voice, finish: () => u.onend?.() }),
    cancel: () => { cancelled++; },
    getVoices: () => voices,
  };
  Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
}

beforeEach(() => { voices = [{ lang: "es-MX", name: "Mexican" }, { lang: "en-US", name: "US" }, { lang: "zh-CN", name: "Mandarin" }]; installFakeSpeech(); });
afterEach(() => { vi.unstubAllGlobals(); Reflect.deleteProperty(window, "speechSynthesis"); });

describe("chunks", () => {
  it("splits lines and sentences, keeps short texts whole, and drops blank lines", () => {
    expect(chunks("bread")).toEqual(["bread"]);
    expect(chunks("Ana: Hi!\n\nBen: Hello.")).toEqual(["Ana: Hi!", "Ben: Hello."]);
    expect(chunks("   ")).toEqual([]);
  });
  it("packs sentences up to a length and splits a very long run with no stops", () => {
    const sentence = "This is a sentence of about forty characters. ";
    const out = chunks(sentence.repeat(10));
    expect(out.length).toBeGreaterThan(1);
    expect(out.every((c) => c.length <= 190)).toBe(true);
    expect(out.join(" ").replace(/\s+/g, " ")).toBe(sentence.repeat(10).trim().replace(/\s+/g, " "));
    expect(chunks("あ".repeat(900)).every((c) => c.length <= 360)).toBe(true);
    expect(chunks("今天天气很好。我们去公园。")).toEqual(["今天天气很好。我们去公园。"]);
  });
});

describe("voiceFor", () => {
  it("matches the exact tag, then the language, and says null when none matches or undefined when voices aren't loaded", () => {
    expect(voiceFor("en")).toMatchObject({ name: "US" });
    expect(voiceFor("es")).toMatchObject({ name: "Mexican" });           // es-ES missing: any Spanish voice
    expect(voiceFor("ja")).toBeNull();
    voices = [];
    expect(voiceFor("en")).toBeUndefined();
  });
});

describe("speak", () => {
  it("reads one chunk after another, in the language's tag at the given rate, then calls onEnd", () => {
    const onEnd = vi.fn();
    speak("Ana: Hi!\nBen: Hello.", "en", SLOW_RATE, { onEnd });
    expect(spoken).toHaveLength(1);
    expect(spoken[0]).toMatchObject({ text: "Ana: Hi!", lang: "en-US", rate: SLOW_RATE });
    spoken[0].finish();
    expect(spoken[1].text).toBe("Ben: Hello.");
    spoken[1].finish();
    expect(onEnd).toHaveBeenCalledTimes(1);
  });
  it("stops reading when the returned stop function is called, and starting a new reading cancels the old one", () => {
    const stop = speak("One.\nTwo.", "en", NORMAL_RATE);
    stop();
    spoken[0].finish();
    expect(spoken).toHaveLength(1);
    expect(cancelled).toBeGreaterThanOrEqual(2);
  });
  it("reports an error when the browser has no speech engine", () => {
    Reflect.deleteProperty(window, "speechSynthesis");
    const onError = vi.fn();
    speak("hello", "en", 1, { onError });
    expect(onError).toHaveBeenCalled();
  });
});

function show(ui: React.ReactElement) {
  return render(ui);
}

describe("SpeakButton", () => {
  it("reads a word when pressed, and the same button stops it", async () => {
    show(<SpeakButton text="bread" language="en" />);
    await userEvent.click(screen.getByRole("button", { name: "Listen to bread" }));
    expect(spoken[0]).toMatchObject({ text: "bread", lang: "en-US" });
    await userEvent.click(screen.getByRole("button", { name: "Stop" }));
    expect(cancelled).toBeGreaterThan(1);
  });
  it("offers a slow reading for stories, at the slow rate", async () => {
    show(<SpeakButton text="Ana: Hi!" language="en" label="Listen" slow />);
    await userEvent.click(screen.getByRole("button", { name: "Listen slowly" }));
    expect(spoken[0].rate).toBe(SLOW_RATE);
  });
  it("says when the device has no voice for the language, but still tries", async () => {
    show(<SpeakButton text="パン" language="ja" />);
    await userEvent.click(screen.getByRole("button", { name: /Listen to/ }));
    expect(await screen.findByText(/No voice for this language/)).toBeInTheDocument();
    expect(spoken[0].lang).toBe("ja-JP");
  });
  it("goes back to idle when the reading ends", async () => {
    show(<SpeakButton text="bread" language="en" />);
    await userEvent.click(screen.getByRole("button", { name: "Listen to bread" }));
    spoken[0].finish();
    await waitFor(() => expect(screen.getByRole("button", { name: "Listen to bread" })).toBeInTheDocument());
  });
  it("renders nothing when the browser cannot speak", () => {
    Reflect.deleteProperty(window, "speechSynthesis");
    const { container } = show(<SpeakButton text="bread" language="en" />);
    expect(container).toBeEmptyDOMElement();
  });
});
