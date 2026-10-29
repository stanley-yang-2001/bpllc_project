import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VoiceSection } from "./VoiceSection";
import { chosenVoiceName } from "../speech/speak";
import { translate } from "../i18n/I18nProvider";

vi.mock("../i18n/I18nProvider", async (orig) => ({
  ...(await orig<typeof import("../i18n/I18nProvider")>()),
  useI18n: () => ({ t: (k: string, p?: Record<string, string | number>) => translate("en", k as never, p) }),
}));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: { languages: ["es", "ja"] } }) }));
vi.mock("../auth/ActiveLanguage", () => ({ useActiveLanguage: () => ({ info: (c: string) => ({ native: c === "es" ? "Español" : "日本語" }) }) }));

const spoken: { text: string; lang: string }[] = [];
beforeEach(() => {
  spoken.length = 0;
  class U { onend: (() => void) | null = null; onerror: null = null; lang = ""; rate = 1; voice: unknown = null; constructor(public text: string) {} }
  vi.stubGlobal("SpeechSynthesisUtterance", U);
  Object.defineProperty(window, "speechSynthesis", {
    configurable: true,
    value: {
      speak: (u: U) => spoken.push({ text: u.text, lang: u.lang }), cancel: () => undefined,
      getVoices: () => [{ lang: "es-ES", name: "Elvira" }, { lang: "es-MX", name: "Dalia" }, { lang: "en-US", name: "Zira" }],
    },
  });
});
afterEach(() => { vi.unstubAllGlobals(); Reflect.deleteProperty(window, "speechSynthesis"); window.localStorage.clear(); });

describe("read-aloud voices in Settings", () => {
  it("offers the device's voices for each studied language and remembers the choice on this device", async () => {
    render(<VoiceSection />);
    const es = screen.getByRole("combobox", { name: "Voice for Español" });
    expect([...es.querySelectorAll("option")].map((o) => o.textContent)).toEqual(["Automatic (best match)", "Elvira (es-ES)", "Dalia (es-MX)"]);
    await userEvent.selectOptions(es, "Dalia");
    expect(chosenVoiceName("es")).toBe("Dalia");
  });
  it("tries a voice out in its own language, and says when a language has no voice", async () => {
    render(<VoiceSection />);
    await userEvent.click(screen.getAllByRole("button", { name: "Test" })[0]);
    expect(spoken[0]).toMatchObject({ lang: "es-ES" });
    expect(screen.getByRole("combobox", { name: "Voice for 日本語" })).toBeDisabled();
    expect(screen.getByText(/no voice for this language/)).toBeInTheDocument();
  });
});
