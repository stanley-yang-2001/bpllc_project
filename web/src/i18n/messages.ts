/** The site's own text in the nine study languages (design 3F). One table, so a reviewer can read all nine languages of a
 * message side by side, and a missing translation does not compile: every entry is a tuple of exactly nine strings in
 * the fixed order below.
 *
 * These translations have NOT had a native-speaker review (design 3F, "open points"). Server messages and the
 * learner's own words are never translated here; the sign-in pages stay in English; the privacy policy is a separate
 * approved copy per language (3I), not a translation made by this file.
 *
 * Plurals use paired keys, `.one` and `.other`, chosen with the browser's Intl.PluralRules (see t.count in i18n.tsx).
 * Placeholders are written {name} and must be identical in all nine entries of a row (a test checks it).
 *
 * The table is split by area (one file in catalog/ each, so a page's text is found next to nothing else). A key lives in
 * exactly one area (a test checks it); to add an area, add a file there and one name to AREAS below. */
import { LOCALES, type Locale, type Nine } from "./catalog/types";
import { shell } from "./catalog/shell";
import { common } from "./catalog/common";
import { errors } from "./catalog/errors";
import { home } from "./catalog/home";
import { vocabulary } from "./catalog/vocabulary";
import { settings } from "./catalog/settings";
import { chat } from "./catalog/chat";
import { studio } from "./catalog/studio";
import { library } from "./catalog/library";
import { practice } from "./catalog/practice";
import { report } from "./catalog/report";
import { setsAndMeanings } from "./catalog/setsAndMeanings";
import { readAloud } from "./catalog/readAloud";
import { pronunciation } from "./catalog/pronunciation";
import { dialogs } from "./catalog/dialogs";

export { LOCALES };
export type { Locale, Nine };

export const AREAS = { shell, common, errors, home, vocabulary, settings, chat, studio, library, practice, report, setsAndMeanings, readAloud, pronunciation, dialogs } as const;
export const MESSAGES = { ...shell, ...common, ...errors, ...home, ...vocabulary, ...settings, ...chat, ...studio, ...library, ...practice, ...report, ...setsAndMeanings, ...readAloud, ...pronunciation, ...dialogs } as const satisfies Record<string, Nine>;

export type MessageKey = keyof typeof MESSAGES;
