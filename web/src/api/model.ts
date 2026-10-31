import { request } from "./http";
import type { MyModel } from "./types";

export const modelApi = {
  myModel: () => request<MyModel>("GET", "/me/model"),
  saveMyModel: (b: { model: string; base_url: string; api_key?: string; remove_key?: boolean }) => request<MyModel>("PUT", "/me/model", { json: b }),
  testMyModel: (b: { model: string; base_url: string; api_key?: string; remove_key?: boolean }) => request<{ ok: boolean }>("POST", "/me/model/test", { json: b }),
  removeMyModel: () => request<void>("DELETE", "/me/model"),
};
