# What the app does, and when each part was built

Dates are the day the work was committed or, for the earliest parts, the date the changelog gives. "Patch" numbers are the delivery files (`git am`) and match `CHANGELOG.md`, which has the full detail, numbers and reasons. **Status** says whether the owner has run it: *Verified* means it passed on the owner's machine in a `run-checks.bat --round` or a live run; *Built* means it was written and tested in the build environment and still waits for a run on the owner's stack. Keep this file current: add a row when a feature ships.

Last updated: 6 November 2026 (through patch 0055).

## Timeline: what was built, day by day

Dates are commit dates (UTC), so a late-evening commit in Chicago can show the next day. The themed tables below give the detail and the verification status.

| Date | What became available |
|---|---|
| 16 Sep to 18 Oct | Story pipeline and tutor Agent, per-learner tools, web app with accounts and isolation, Story Studio, Library, quality report, practice, preferences, nine site languages, privacy policy as data |
| 19 Oct | Chat story tool takes a kind and a topic (own kinds allowed); non-English story prompts use the learner's own word list |
| 20 Oct | Least-privilege database role for the Langflow tools (migration 0008); "story" alone is not a kind |
| 21 Oct | User ID on Settings; routing cases for kind and topic; plainer English variety |
| 22 Oct | Language check for own-language word lists; browser tests for the picker and User ID |
| 23 Oct | Stories enabled in German, Italian, Portuguese, Chinese and Korean |
| 24 Oct | Custom topic in Studio; fill-in-the-blank for Chinese, Japanese, Korean; chat in the study language (0010); difficulty tiers; own model for stories (0011); everyday-word lists for nine languages |
| 25 Oct | Length and ending fixes for CJK; cut-off ending check; scored vocabulary outside English; chat story difficulty; kanban script |
| 26 Oct | Word sets (0012); multiple choice; tutor-written meanings; read aloud; pronunciation guides and translation; sets ticked in the site limit chat stories |
| 27 Oct | SOLID refactor, diagrams |
| 28 Oct | One command for every test (`run-checks.bat`) |
| 29 Oct | Meaning language (0013); voice picker; remembered practice with streak (0014); starter packs and first-run guide; dictation; CI workflow |
| 30 Oct | `run-checks.bat --round`; parts of speech (0015); richer English kinds switch; back-end splits B3 to B9 |
| 31 Oct | Splits B10 to B12 and F1 to F9; backlog round |
| 1 Nov | CJK stray words scored (rules 5); letter sign-offs (rules 6); phase 2 spike |
| 2 Nov | Spike and test fixes |
| 3 Nov | One REPORT.txt per run; chat on your own model (option B); own-model failure notice in chat; streaming behind a switch; kanban board generator |
| 4 Nov | Streaming probe, then streaming parked (off) |
| 5 Nov | Automatic own-model chat check; length for chat stories (up to 400 words); round fixes; more reliable story kinds in chat |
| 6 Nov | Features document, PR description, privacy policy options (docs only); grammar checks and repair for generated stories (0055) |

## 1. The foundation (September to 18 October 2026)

| Feature | Date | What it does | Status |
|---|---|---|---|
| Story pipeline and language agent | 16 Sep to 2 Oct | The first Langflow flow: a tutor Agent that adds words and writes stories from the learner's word list, with a deterministic router. | Verified |
| Tool Result Relay, routing tests (Steps 9 and 10) | October | The tutor's tool output reaches the learner exactly as the tool wrote it; an automatic matrix checks the right tool and arguments for each request. | Verified |
| Per-learner tools (M3) | 14 Oct | `tutor_core` holds the tool logic; each tool call is for one learner and refuses (fails closed) when it does not know who. | Verified |
| Web app, accounts, isolation (M1, M2, M4, M5) | by 15 Oct | React site, email sign-up with consent, one sign-in cookie, sessions, a salt per password, "learner B cannot see learner A" tests, deleting an account also deletes the learner's Langflow chat, a tokens-per-minute limiter. | Verified |
| Story Studio, Library, Quality report (M6) | 16 Oct | Make a story from your words, check it automatically (vocabulary, language, length, format), save it to a Library. | Verified |
| Practice and demo walkthrough (M7) | 16 Oct | Flashcards and fill-in-the-blank from a saved story. | Verified |
| Preferences, site language, themes, privacy policy as data (M8) | 17 to 18 Oct | Display name, nine site languages, seven themes and a colour wheel saved on the account, a privacy policy served as approved per-language copies. | Verified |

## 2. Chat with the tutor

| Feature | Date | What it does | Status |
|---|---|---|---|
| Story tool takes a kind and a topic | 19 Oct | In chat, "a dialogue in Spanish" or "a letter about a market" reaches the story tool as kind and topic; a learner may write a kind of their own. The plain word "story" is not a kind (fixed 20 Oct). | Verified |
| Chat replies in the study language | 24 Oct | A setting (migration 0010) makes the tutor write its own sentences in the language you study. | Verified |
| A language named in chat wins | 24 Oct | A story in a language the learner names is written in it, and re-tried once when the first try comes out in the wrong language. | Verified |
| Chat story difficulty | 25 Oct | "An easy story" reaches the tool as easy, medium or hard. | Verified |
| Sets ticked in the site limit chat stories | 26 Oct | The story tool only uses the word sets ticked on the site (hidden `set_ids` input). | Verified |
| Own-model failures shown in chat | 3 Nov | When a call to your own model fails but the tutor still answers, a note gives the provider's reason (key removed). Nine languages. | Built |
| Length for chat stories | 5 Nov | "A 300-word story" or "more than 400 words" reaches the tool as a number of words, kept between 20 and 400. | Verified by routing case L1; by-hand check pending |
| More reliable story kinds | 5 Nov | Clearer Agent instructions and tool hint so a named kind (dialogue, conversation, letter, diary, poem...) reaches the tool; new routing cases and repeated runs with printed pass rates. | Built |

## 3. Stories and their quality

| Feature | Date | What it does | Status |
|---|---|---|---|
| Stories in all nine languages | 23 Oct | Enabled German, Italian, Portuguese, Chinese and Korean after measuring 15 of 15 each. | Verified |
| Plainer English variety | 21 to 23 Oct | English with no kind named gives narration or dialogue; other languages keep all eight kinds; short word lists get only classic styles. | Verified |
| Difficulty tiers | 24 Oct | Easy (about 60 words, 3 of your words, at most 5% unusual), Medium, Hard, or Custom with your own numbers (length 20 to 400). Measured in the quality report. | Verified |
| Everyday-word lists for nine languages | 24 Oct | Word lists (6,000 words each for German, Italian, Portuguese and the others) so common words do not count as "unusual"; a splitter for Chinese, Japanese, Korean. | Verified |
| Custom topic in Studio | 24 Oct | "Write my own..." topic, with the same limits and quoting as a custom kind. | Verified |
| Length and ending fixes | 24 to 25 Oct | Chinese, Japanese and Korean lengths, one more try when the length is far off, cut-off and dangling endings caught, language check for short texts. | Verified |
| Quality rules, stray words | 25 Oct to 1 Nov | Vocabulary scored outside English; Chinese, Japanese and Korean strays scored too (rules version 5); letter sign-offs finish a story (version 6). | Verified |
| Grammar and fluency of stories | 6 Nov | Code checks for list-like, repeated and monotonous sentences; one repair call that names the problem; optional grammar proofreading call (`STORY_PROOFREAD=1`); a natural-sentence rule in non-English prompts. A rewrite is used only if still in the language, complete, about as long and keeping your words. | Built |
| Richer English kinds | 30 Oct | Diary, letter and place stories can return to random picks behind `TUTOR_RICH_RANDOM`, after a stray-word retry. | Verified (check passes; switch off by default) |

## 4. Vocabulary, practice and reading aloud

| Feature | Date | What it does | Status |
|---|---|---|---|
| Word sets | 26 Oct | Group words into sets (migration 0012); stories and practice can use chosen sets. | Verified |
| Multiple-choice practice | 26 Oct | Pick the meaning of a word, alongside flashcards and fill-in-the-blank (all languages from 24 Oct). | Verified |
| Meanings written by the tutor | 26 Oct | "Write missing meanings" fills in blanks; from 29 Oct in the language you choose (migration 0013). | Verified |
| Read aloud | 26 Oct | Speaker buttons for words and stories using your browser's voices; a voice picker per language (29 Oct). | Verified; by-hand check |
| Pronunciation guides and translation | 26 Oct | Pinyin, romaji, Korean romanization from libraries, IPA for the other languages; translate words or story lines. Shown, never stored. | Verified |
| Remembered practice | 29 Oct | Spaced review: each word has a box, a due time and right/wrong counts (migration 0014); "Due now / New / Learning / Known" progress card; a daily streak. | Verified |
| Starter packs and first-run guide | 29 Oct | A new learner adds a ready word pack from Home and follows a three-step guide. | Verified |
| Dictation | 29 Oct | Hear a word, type it; three kinds of feedback. | Verified; by-hand check |
| Parts of speech | 30 Oct | A part-of-speech label for every word (per-language choices, such as i-adjective for Japanese), set by hand or by the tutor, plus a practice for them (migration 0015). | Verified |

## 5. Your own AI model

| Feature | Date | What it does | Status |
|---|---|---|---|
| Own model for stories (phase 1) | 24 Oct | An account the operator switches on saves a model name, address and API key (encrypted); the address is checked so it cannot reach private networks. | Verified |
| Own model for meanings, labels, translation, pronunciation | 26 Oct to 30 Oct | The same model answers those features instead of the shared one. | Verified |
| Chat on your own model (phase 2, option B) | 3 Nov | Behind `CHAT_OWN_MODEL=1`: the API plays the model for Langflow, so the key stays on the API; one-turn throwaway codes; no fallback to the shared model. | Verified by the fake-provider check (5 Nov); real-provider check pending |
| Automatic own-model chat check | 5 Nov | `own-model-chat-live` in the round: key reaches the provider only from the API, wrong key is refused, key is in no table. | Verified (passed 5 Nov) |

## 6. Accounts, privacy and safety

| Feature | Date | What it does | Status |
|---|---|---|---|
| Least-privilege tools role | 19 to 20 Oct | The Langflow tools connect as `tutor_tools`, which can read words and add words and nothing else (migration 0008). | Verified |
| User ID on Settings | 21 Oct | Settings shows the learner's own ID for the checking scripts. | Verified |
| Data download includes practice | 29 Oct | "Download my data" lists every table with your data, including practice progress; a test fails if a new table is missing from it. | Verified |
| Privacy policy options | 5 Nov | `docs/PRIVACY-POLICY-OPTIONS.md`: where the approved wording differs from the code, with wording to choose from. Nothing is live. | Waiting for your choice |

## 7. Quality of the build itself

| Feature | Date | What it does |
|---|---|---|
| SOLID refactors | 27 Oct, 29 to 31 Oct | Big files split into small parts (back end B1 to B12, front end F1 to F9) without changing behaviour; class diagrams updated. |
| One command for every test | 28 Oct | `scripts/run_all_checks.py` and `run-checks.bat`: unit tests, a throwaway stack, live checks; a CI workflow (29 Oct). |
| `run-checks.bat --round` | 30 Oct | One round with a single `REPORT.txt` to send back (from 3 Nov), the manual checklist, and (5 Nov) the lines of any failure quoted. |
| Kanban board | 25 Oct, 3 Nov | `docs/kanban/cards.json` is the source; `scripts/make_board.py` writes `BOARD.md`. |
| Live checks | 28 Oct to 5 Nov | Text tools, meanings, parts of speech, richer kinds, routing, own-model chat. |
| Streaming chat reply (parked) | 3 to 4 Nov | Built behind `CHAT_STREAM=1`; the probe showed Langflow's Agent sends no word-by-word events, so it is off and in the backlog. |

## Where to read more

- `CHANGELOG.md`: every patch with its numbers and reasons.
- `docs/CUSTOM-MODEL-DESIGN.md`: own model, option B, streaming result.
- `docs/DIFFICULTY-TIERS-DESIGN.md`: tiers and chat length.
- `docs/AGENT-INSTRUCTIONS.md`: the tutor's instructions and why they read as they do.
- `docs/TESTING.md`: the checks and how to run them.
- `docs/kanban/BOARD.md`: what is done, in review and in the backlog.
