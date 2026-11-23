import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../auth/AuthContext";
import { ToastProvider } from "../components/Toast";
import { ALICE, err, LANGS, mockApi, renderIn } from "../test/helpers";
import EMOJI from "./emojis.json";
import { PictureButton } from "./PictureButton";
import { PictureThumb } from "./PictureThumb";
import { GlossedText } from "../reader/GlossedText";
import { WordTable } from "../vocab/WordTable";
import { PhotoUnreadable } from "./shrink";

const shrink = vi.hoisted(() => ({ fn: vi.fn() }));
vi.mock("./shrink", async (orig) => ({ ...(await orig<typeof import("./shrink")>()), shrinkPhoto: shrink.fn }));

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); shrink.fn.mockReset(); });

const base = { "GET /me": ALICE, "GET /languages": LANGS };
const BREAD = "\u{1F35E}";
const EMOJI_PIC = { kind: "emoji", emoji: BREAD, url: null, thumb_url: null } as const;
const PHOTO_PIC = { kind: "photo", emoji: null, url: "/api/words/7/picture?v=1", thumb_url: "/api/words/7/picture?v=1&size=thumb" } as const;
function SignedIn({ children }: { children: React.ReactNode }) { return useAuth().user ? <>{children}</> : null; }
const show = (picture: typeof EMOJI_PIC | typeof PHOTO_PIC | null = null) =>
  renderIn(<ToastProvider><SignedIn><PictureButton word={{ id: 7, word: "bread", picture }} language="en" /></SignedIn></ToastProvider>);
const calls = (c: ReturnType<typeof mockApi>["calls"], method: string) => c.filter((x) => x.method === method);

describe("the picture of a word", () => {
  it("draws an emoji as text and a photo as the small copy, both hidden from screen readers", () => {
    const { container, rerender } = renderIn(<PictureThumb picture={EMOJI_PIC} />).ui;
    expect(container.querySelector("span[aria-hidden]")!.textContent).toBe(BREAD);
    rerender(<PictureThumb picture={PHOTO_PIC} />);
    expect(container.querySelector("img")!.getAttribute("src")).toBe(PHOTO_PIC.thumb_url);
    rerender(<PictureThumb picture={PHOTO_PIC} size="lg" />);
    expect(container.querySelector("img")!.getAttribute("src")).toBe(PHOTO_PIC.url);
    expect(container.querySelector("img")!.getAttribute("alt")).toBe("");
  });

  it("offers to add a picture to a word without one and to change the picture of a word that has one", async () => {
    mockApi(base);
    show();
    expect(await screen.findByRole("button", { name: "Add a picture for bread" })).toBeInTheDocument();
  });

  it("says change when the word already has a picture", async () => {
    mockApi(base);
    show(EMOJI_PIC);
    expect(await screen.findByRole("button", { name: "Change the picture of bread" })).toBeInTheDocument();
  });

  it("saves the emoji that was clicked and closes", async () => {
    const m = mockApi({ ...base, "PUT /words/7/picture/emoji": EMOJI_PIC });
    show();
    await userEvent.click(await screen.findByRole("button", { name: "Add a picture for bread" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: BREAD }));
    await waitFor(() => expect(calls(m.calls, "PUT")).toHaveLength(1));
    expect(calls(m.calls, "PUT")[0]).toMatchObject({ path: "/words/7/picture/emoji", body: { emoji: BREAD } });
    expect(await screen.findByText("Picture saved")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("saves an emoji that was typed, and only when something was typed", async () => {
    const m = mockApi({ ...base, "PUT /words/7/picture/emoji": EMOJI_PIC });
    show();
    await userEvent.click(await screen.findByRole("button", { name: "Add a picture for bread" }));
    const use = screen.getByRole("button", { name: "Use this emoji" });
    expect(use).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Or type or paste any emoji"), "\u{1F9C0}");
    await userEvent.click(use);
    await waitFor(() => expect(calls(m.calls, "PUT")[0].body).toEqual({ emoji: "\u{1F9C0}" }));
  });

  it("shows the server's reason and stays open when an emoji is refused", async () => {
    mockApi({ ...base, "PUT /words/7/picture/emoji": err(422, "validation_error", "Choose one emoji.") });
    show();
    await userEvent.click(await screen.findByRole("button", { name: "Add a picture for bread" }));
    await userEvent.type(screen.getByLabelText("Or type or paste any emoji"), "abc");
    await userEvent.click(screen.getByRole("button", { name: "Use this emoji" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose one emoji.");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("makes a chosen photo small and sends that, not the file itself", async () => {
    const small = new Blob(["small"], { type: "image/jpeg" });
    shrink.fn.mockResolvedValue(small);
    const m = mockApi({ ...base, "PUT /words/7/picture/photo": PHOTO_PIC });
    show();
    await userEvent.click(await screen.findByRole("button", { name: "Add a picture for bread" }));
    const original = new File(["x".repeat(5000)], "holiday.heic", { type: "image/heic" });
    await userEvent.upload(screen.getByLabelText("Choose a photo"), original);
    await waitFor(() => expect(calls(m.calls, "PUT")).toHaveLength(1));
    expect(shrink.fn).toHaveBeenCalledWith(original);
    const sent = calls(m.calls, "PUT")[0].body.file as File;
    expect(sent.size).toBe(small.size);
    expect(sent.name).toBe("photo.jpg");
    expect(calls(m.calls, "PUT")[0].headers["X-Requested-With"]).toBe("tutor");
  });

  it("tells the learner when the browser cannot read the photo, and sends nothing", async () => {
    shrink.fn.mockRejectedValue(new PhotoUnreadable());
    const m = mockApi(base);
    show();
    await userEvent.click(await screen.findByRole("button", { name: "Add a picture for bread" }));
    await userEvent.upload(screen.getByLabelText("Choose a photo"), new File(["x"], "a.heic", { type: "image/heic" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This picture could not be read");
    expect(calls(m.calls, "PUT")).toHaveLength(0);
  });

  it("explains what is done to a photo, and removes a picture on request", async () => {
    const m = mockApi({ ...base, "DELETE /words/7/picture": () => ({ status: 204 }) });
    show(PHOTO_PIC);
    await userEvent.click(await screen.findByRole("button", { name: "Change the picture of bread" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/camera and location details are removed/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove the picture" }));
    await waitFor(() => expect(calls(m.calls, "DELETE")).toHaveLength(1));
    expect(await screen.findByText("Picture removed")).toBeInTheDocument();
  });

  it("offers no remove button for a word with no picture", async () => {
    mockApi(base);
    show();
    await userEvent.click(await screen.findByRole("button", { name: "Add a picture for bread" }));
    expect(screen.queryByRole("button", { name: "Remove the picture" })).not.toBeInTheDocument();
  });
});

describe("the emoji grid", () => {
  it("has the six groups, none empty and no emoji twice", () => {
    expect(Object.keys(EMOJI)).toEqual(["food", "nature", "people", "places", "things", "signs"]);
    const all = Object.values(EMOJI).flat();
    expect(all.length).toBeGreaterThan(150);
    expect(new Set(all).size).toBe(all.length);
  });
});

describe("where the picture shows", () => {
  const word = (id: number, w: string, picture: typeof EMOJI_PIC | null) => ({ id, language: "en", word: w, meaning: "a food", pos: null, set_id: null, created_at: "2026-01-01T00:00:00Z", picture });
  it("is a column of the word list, with a button for every word", async () => {
    mockApi({ ...base, "GET /words/parts-of-speech": { language: "en", items: [] } });
    renderIn(<ToastProvider><SignedIn><WordTable words={[word(1, "bread", EMOJI_PIC), word(2, "cheese", null)]} language="en" selected={new Set()} onToggle={() => undefined}
      onToggleAll={() => undefined} readings={new Map()} showReadings={false} setNames={null} /></SignedIn></ToastProvider>);
    expect(await screen.findByRole("button", { name: "Change the picture of bread" })).toHaveTextContent(BREAD);
    expect(screen.getByRole("button", { name: "Add a picture for cheese" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Picture" })).toBeInTheDocument();
  });

  it("is on the reader's card next to the meaning, with a button to change it", async () => {
    mockApi({ ...base, "POST /reading/gloss": { spans: [{ start: 8, end: 13, word_id: 1 }], words: [{ id: 1, word: "bread", meaning: "a food", pos: null, picture: EMOJI_PIC }] } });
    renderIn(<ToastProvider><SignedIn><GlossedText text="She ate bread." language="en" /></SignedIn></ToastProvider>);
    await userEvent.click(await screen.findByRole("button", { name: "bread" }));
    const card = within(screen.getByRole("region", { name: "About this word" }));
    expect(card.getByText("a food")).toBeInTheDocument();
    expect(card.getAllByText(BREAD).length).toBeGreaterThan(0);
    expect(card.getByRole("button", { name: "Change the picture of bread" })).toBeInTheDocument();
  });
});
