import { request } from "./http";
import type { ChatReply } from "./types";

export const chatApi = {
  chat: (b: { message: string; language: string; session_id: string; set_ids?: number[] }) => request<ChatReply>("POST", "/chat", { json: b }),
};
