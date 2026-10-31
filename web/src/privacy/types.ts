/** The shape of one policy copy as the API serves it (api/app/policy/*.json). */
export type Block =
  | { type: "p"; text: string; text_without_contact?: string }
  | { type: "list"; items: string[] }
  | { type: "table"; caption: string; head: string[]; rows: string[][] };

export interface PolicyDoc {
  title: string;
  summary: { title: string; items: string[] };
  sections: { id: string; title: string; blocks: Block[] }[];
  governing: string;
}
