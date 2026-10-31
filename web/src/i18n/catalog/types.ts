export const LOCALES = ["en", "es", "fr", "de", "it", "pt", "ja", "zh", "ko"] as const;
export type Locale = (typeof LOCALES)[number];
/** One message: its text in the nine languages, in the order of LOCALES. A row with fewer or more strings does not compile. */
export type Nine = readonly [string, string, string, string, string, string, string, string, string];
