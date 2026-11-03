import { request } from "./http";
import type { ChatReply } from "./types";

export const chatApi = {
  /** `onDelta` is called with the tutor's words as they are written, when the API streams; the returned reply is always the complete one. */
  chat: (b: { message: string; language: string; session_id: string; set_ids?: number[] }, onDelta?: (text: string) => void) =>
    request<ChatReply>("POST", "/chat", { json: b, onDelta }),
};
