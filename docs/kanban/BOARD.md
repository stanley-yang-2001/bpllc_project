# Kanban board

Generated from `cards.json` (the same file `scripts/create_kanban_cards.py` uploads). Done = built and run or verified; In review = built, waiting for your run; Backlog = not built.


## Backlog (31)

- **Chat on your own model (phase 2)** (no date) — Needs a spike on the author's machine first (how the Agent calls a user-supplied model).
- **Saved story remembers which model wrote it** (no date) — Store the model name with a saved story and show it in the Library.
- **Difficulty option for the chat story tool** (no date) — Let the chat tool pass a tier so a chat story can be Easy, Medium or Hard.
- **Language check: very short English text can pass as a Latin-script language** (no date) — With few words no English marker fires. Needs a positive check (accents, function words) and tests.
- **Vocabulary adherence for non-English lists** (no date) — Strays are listed but not scored outside English. The everyday lists now make a scored rule possible.
- **Native review of the nine-language site text and policy copies** (no date) — Translations are machine-written and not reviewed by native speakers; policy copies are shown only when approved.
- **Install splitter and lemma packages in the Langflow image** (no date) — Only the API image has the [cjk] and [lemmas] extras.
- **Richer English kinds back into random picks** (no date) — Regenerate once when the check fails so diary, letter and place stories can return to random choice.
- **Merge the duplicated add-word INSERT** (no date) — The same INSERT exists in two places.
- **Push the branch and open the pull request** (no date) — The author pushes to the remote; the branch has 30+ local commits.
- **B1: Move the story-making use case out of the stories route** (2026-10-27) — routes/stories.py holds the whole generate flow and the request models. Move the flow to services/story_generation.py and the models to schemas so the route only calls it.
- **B2: One set-filter clause instead of three copies** (2026-10-27) — The same all/general/set-id SQL clause is written in vocab.list_words, vocab.words_without_meaning and practice._set_clause.
- **B3: Move the chat turn out of the chat route; give the chat client an interface** (2026-10-27) — routes/chat.py holds the gate slot, session record, preference read and reply language, and reads calls_ai and stores_chat with getattr.
- **B4: Move the own-model settings logic out of the model route** (2026-10-27) — routes/model.py does the test, save and remove steps with encryption and the address check inline.
- **B5: Split user_model.py into address guard, pinned HTTP, client and rate limit** (2026-10-27) — services/user_model.py (160 lines) has four jobs: the SSRF address check, the pinned connections, the chat-completions call and the request limiter.
- **B6: Split vocab.py: CSV import and meaning helpers** (2026-10-27) — services/vocab.py (172 lines) mixes word CRUD, meaning filling, CSV parsing and bulk insert.
- **B7: Turn practice.py into a practice package** (2026-10-27) — services/practice.py (192 lines) holds flashcards, multiple choice and fill-in-the-blank. Each mode gets its own module so a new mode is a new file.
- **B8: Split schemas.py by area** (2026-10-27) — schemas.py (204 lines, 29 models) is one file for every response model.
- **B9: Break up generate_story in tutor_core** (2026-10-27) — generate_story has 12 parameters and 82 lines: gate, cache, load, prompt, model call and two retry policies. _better_try reads the private difficulty._UNSPACED.
- **B10: Turn check_passage into a list of small rules** (2026-10-27) — quality/passage.check_passage is the longest function in the repo (118 lines, 12 parameters). Each rule becomes a function; a runner combines them.
- **B11: One parser for Langflow tool output** (2026-10-27) — custom_components/tool_result_relay.py and api/app/services/langflow/reply.py each parse a tool's recorded output with their own copy of output_to_text and the block walker.
- **B12: Split security.py and difficulty.py into packages** (2026-10-27) — security.py mixes password hashing, tokens and the login guard; difficulty.py mixes presets, the prompt note and measuring.
- **F1: Split the API client by area** (2026-10-27) — web/src/api/client.ts is one object with 43 calls, so every page depends on all of them.
- **F2: Split Story Studio** (2026-10-27) — Studio.tsx (232 lines) has 10 states, 5 queries and mutations, the difficulty presets and the custom-kind logic.
- **F3: Split the Login page into LoginForm and RegisterForm** (2026-10-27) — Login.tsx (187 lines) holds two forms and their field helpers.
- **F4: Serve the difficulty sizes from the API** (2026-10-27) — The Easy, Medium and Hard numbers and limits are written in Studio.tsx and again in tutor_core/difficulty.py.
- **F5: Split the Chat page** (2026-10-27) — Chat.tsx (153 lines) holds the message list, the composer, the retry and the story-save button.
- **F6: One StoryMeta component for kind, topic and difficulty** (2026-10-27) — Studio and Library both render a story's kind, topic and difficulty with the same three label helpers.
- **F7: Split the message table by area** (2026-10-27) — i18n/messages.ts is one 471-line table for the whole site.
- **F8: Separate saving from holding in PreferencesProvider** (2026-10-27) — PreferencesProvider.tsx (162 lines) holds the value, debounces saves, retries and writes the device copy.
- **F9: Split Library and Privacy into parts** (2026-10-27) — Library.tsx (129 lines) holds the list, row, opened story and delete flow; Privacy.tsx (131 lines) holds a block renderer.

## In review (11)

- **Known gaps pass: heading above a narration, closing line, grammar rule** (2026-10-25) — 'Montag Morgen:' is no longer read as a speaker; target-language stories get a rule to end with the story and re-check articles, verb endings and agreement (patch 0024).
- **Your own AI model for stories (phase 1)** (2026-10-24) — Per-account switch, encrypted key (MODEL_KEY_SECRET), address guard, My model card, report names the model. Built and tested here, applied; not yet run with a real key.
- **Vocabulary sets (general plus your own)** (2026-10-26) — Learners group words into named sets; the original list is the General set.
- **Choose sets for stories in Studio and Chat** (2026-10-26) — Tick which sets feed a story; General is always available.
- **Multiple choice practice** (2026-10-26) — Four options per question from the learner's own words with meanings.
- **Tutor-written meanings** (2026-10-26) — The model writes meanings for new words and for every word without one.
- **Translate vocabulary and stories between two languages** (2026-10-26) — Translate a word list entry or a story into another language, in chat, Library and Vocabulary.
- **Pronunciation guides (IPA, pinyin, romaji, romanization)** (2026-10-26) — Show how a word or story is read: IPA for English and other alphabetic languages, pinyin for Chinese, romaji and kana for Japanese, romanization for Korean.
- **Read aloud (text to speech)** (2026-10-26) — A button to hear a word or a story in the study language.
- **SOLID refactor of the new and existing code** (2026-10-27) — Apply single-responsibility, open/closed and dependency-inversion where there was a real reason, without changing behaviour.
- **Update the docs diagrams and add class diagrams** (2026-10-27) — Rewrite the architecture, use-case, concept, workflow and state diagrams for the current site; add back-end and front-end class diagrams and a database diagram.

## Done (33)

- **Project start: repo, documentation, architecture diagrams** (2026-09-16) — Initial commit, overview, use-case, class, state, workflow, concept and architecture diagrams, learning objectives, style guide.
- **Environment check: Docker, Postgres, Groq (Steps 1–2, 4–5)** (2026-09-21) — Docker compose stack with Langflow and Postgres; smoke test for Postgres and the Groq key; Language Agent.
- **Story pipeline components (Steps 6–8)** (2026-09-25) — Word upload, story prompt builder, guard and final-passage extractor as Langflow components.
- **Reliability work and deterministic router (Steps 8–9)** (2026-10-02) — Fixes for empty story output and a deterministic routing step before the agent.
- **Agent orchestration with Tool Result Relay (Step 9)** (2026-10-05) — Agent picks the tool; the relay returns tool output verbatim; verified in the Playground.
- **Step 10: measure the tools (routing tests, story batch, language check)** (2026-10-08) — Automated routing tests, story batch runner, vocabulary adherence checker, language-aware story prompt, story variety tuning; LO 8 verdict drafted.
- **Web app design v4 (React + FastAPI)** (2026-10-10) — Design document with milestones M0–M8, threat model, privacy decisions, confirmed decisions; revised for account preferences and translated policy.
- **M0: verify the Langflow assumptions** (2026-10-14) — Each tool gets its own learner input per request (node-id tweak key, hidden input not named user_id); real responses saved as fixtures; chat deletion probe.
- **M1: API skeleton and site shell** (2026-10-12) — FastAPI app, React/Vite shell, compose service, health checks with Langflow and Groq lines, OpenAPI types.
- **M2: accounts and login** (2026-10-13) — Email sign-up with consent, sessions, per-account password salt, login guard, isolation tests, privacy policy page.
- **M3: shared tutor_core and per-learner tools** (2026-10-14) — Story, vocabulary and quality logic moved out of Langflow into tutor_core; Langflow tools refuse to run without a learner id; verified live (m3_check).
- **M4: vocabulary page and API** (2026-10-13) — Per-language word lists, search, add, edit, delete, CSV upload, starter words.
- **M5: chat, chat deletion, token limiter** (2026-10-15) — Live chat through Langflow, deleting an account removes its Langflow conversation, tokens-per-minute limiter, per-account password salt, privacy wording and prompt-privacy test.
- **M6: Story Studio and quality report** (2026-10-16) — Story type and topic, quality report (language, structure, strays), token charge, save to library.
- **M7: Library, Practice and demo walkthrough** (2026-10-16) — Saved stories with badges, flashcards, fill-in-the-blank, demo seed account, browser tests.
- **M8: display names, preferences on the account, site language, themes, policy copies** (2026-10-17) — Nine-language site catalog, seven theme presets and a custom colour wheel with a readability panel, account preferences (migration 0007), policy served as data with approved copies.
- **Least-privilege database role for the Langflow tools (migration 0008)** (2026-10-20) — tutor_tools role can only SELECT/INSERT what the tools need; confirmed working on the author's machine.
- **Remove the old Step 8 canvas components** (2026-10-19) — Four components and their tests deleted; docs updated.
- **Non-English story prompt (target-language variant)** (2026-10-19) — The prompt says the list is already in the target language; Spanish 14/15, French 15/15, Japanese 15/15.
- **Chat story tool takes a kind and a topic** (2026-10-19) — Dialogue, letter and a kind of the learner's own reach the tool (routing cases T1–T3); 'story' alone names no kind.
- **Settings shows the learner's User ID** (2026-10-21) — Account card with the id used by the checking scripts.
- **English stories: classic styles unless a kind is asked for** (2026-10-21) — Richer kinds failed the stray-word check; random picks are narration or dialogue.
- **Five more languages switched on: German, Italian, Portuguese, Chinese, Korean** (2026-10-23) — Each measured 15/15 in the requested language; checker fixed for non-English word lists (German 1/15 → 14/15).
- **Custom topic, fill-in-the-blank for Chinese/Japanese/Korean, chat replies in study language** (2026-10-24) — Write-your-own topic, cloze for all languages, account checkbox for chat replies in the study language (migration 0010).
- **Story difficulty tiers (Easy / Medium / Hard / Custom)** (2026-10-24) — Length, own words and unusual-word share asked and measured; report rows; Library badge; design in docs/DIFFICULTY-TIERS-DESIGN.md.
- **One story call per chat reply** (2026-10-24) — A reply showed three 'Used Story Generator Tool' chips; the API now keeps only the call matching the reply. Confirmed one chip.
- **Everyday-word lists for nine languages (6000 each) and the stray rule** (2026-10-24) — Lists kept in the backend (wordfreq, CC BY-SA 4.0); everyday words outside the learner's list are no longer strays; learners may still add any word.
- **Chinese / Japanese / Korean word splitter and uncommon-word share** (2026-10-24) — rjieba, janome, kiwipiepy; own words matched by word; boundary-aware fill-in-the-blank; chunks made of everyday words are not unusual.
- **Privacy policy: your own AI model sentence and version bump** (2026-10-24) — Sentence approved by the author; policy version 2026-10-24, every learner accepts again.
- **Difficulty tiers tuned for zh/ja/ko (retry, bigger ask, token room)** (2026-10-25) — From the author's runs of difficulty_check.py: 18 of 18 Chinese/Japanese/Korean Medium and Hard stories passed after patches 0021–0023.
- **difficulty_check.py: generate and measure stories at each tier** (2026-10-25) — Signs up a throwaway learner, makes stories per language and tier through the real API, prints asked vs measured, deletes the learner.
- **Repo cleanup and ENVIRONMENT.md** (2026-10-24) — Removed .env.example and relay_debug.log; docs/ENVIRONMENT.md lists every setting.
- **Test suites: core, API, web, container, browser, routing matrix** (2026-10-25) — Automated tests (core 311, API 808, web 233) plus live checks (routing matrix 18/18, browser tests 52/52).
