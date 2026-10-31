/** The API client. One object (`api`) for the pages; the calls live in one file per area (account, words, stories, practice, chat,
 * model, text) and the shared request code in http.ts. Everything the pages import from here still comes from here. */
import { accountApi } from "./account";
import { chatApi } from "./chat";
import { modelApi } from "./model";
import { practiceApi } from "./practice";
import { storiesApi } from "./stories";
import { textApi } from "./text";
import { wordsApi } from "./words";

export * from "./types";
export { ApiError, setCurrentUserId } from "./http";

export const api = { ...accountApi, ...modelApi, ...wordsApi, ...storiesApi, ...practiceApi, ...chatApi, ...textApi };
