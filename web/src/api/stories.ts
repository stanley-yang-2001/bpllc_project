import { qs, request } from "./http";
import type { StoryOptions, DifficultyChoice, GeneratedStory, SavedStory, StoryPage } from "./types";

export const storiesApi = {
  storyOptions: () => request<StoryOptions>("GET", "/stories/options"),
  generateStory: (b: { language: string; story_type?: string; topic?: string; set_ids?: number[] } & DifficultyChoice) =>
    request<GeneratedStory>("POST", "/stories/generate", { json: b }),
  saveStory: (b: { language: string; body: string; story_type?: string | null; topic?: string | null; model?: string | null } & DifficultyChoice) =>
    request<SavedStory>("POST", "/stories", { json: b }),
  stories: (p: { language?: string; limit?: number; offset?: number }) => request<StoryPage>("GET", `/stories?${qs(p)}`),
  story: (id: number) => request<SavedStory>("GET", `/stories/${id}`),
  deleteStory: (id: number) => request<void>("DELETE", `/stories/${id}`),
};
