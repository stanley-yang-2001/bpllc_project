# Demo walkthrough

A five-minute tour of the app from a clean checkout. It runs entirely on the built-in practice tutor (`AI_MODE=stub`), so it
needs **no Groq key and no Langflow setup**. The stories in this mode are one fixed dialogue; the quality report, saving,
the library and practice are the real code.

## Set up

1. Create `.env` (see `docs/ENVIRONMENT.md`) and set:
   ```
   JWT_SECRET=<at least 32 random characters>
   AI_MODE=stub
   DEMO_EMAIL=demo@example.com
   DEMO_PASSWORD=<at least 8 characters>
   ```
2. Start the stack: `docker compose up -d --build` (the first build is slow because Langflow's image is built too).
3. Create the demo account: `docker compose exec api python -m app.seed`. It prints how many words and stories it made and
   is safe to run again. The account gets about 60 English words, 10 Spanish words and one short saved story in each.
4. Open http://localhost:8080 and log in with the demo email and password.

## The tour

| Step | Where | What to show | What it proves |
|---|---|---|---|
| 1 | Home | The cards for each page and your word count | Everything is the logged-in learner's own |
| 2 | Vocabulary | Search, add a word with a meaning, edit a meaning, upload `sample_data/suggested_words.csv` | Per-language lists, CSV rules |
| 3 | Studio | Pick "Story" and a topic, Make a story, read the quality report | Language check, shape check, words outside your list |
| 4 | Studio | Make another, then Save to library | A new story each time; nothing is kept until you save |
| 5 | Library | Open the story you saved and the seeded one; the verdict badge and the report | Saved stories keep their report |
| 6 | Practice | Fill in the blank on a story: choose, see the answer, finish for a score | Blanks are only words from your own list |
| 7 | Practice | Flashcards: show the meaning, "I knew it" or "Not yet" | Shuffled words that have a meaning |
| 8 | Chat | Ask for "add the word bread", then "tell me a story"; use Save story to library | The tool trace; the chat story lands in the Library |
| 9 | Spanish | Switch the active language to Spanish and repeat Library and Practice | Per-language lists and stories |
| 10 | Settings | Services (Postgres up; Langflow and Groq say they use the built-in tutor), Download my data, then Delete account | Export includes stories; deleting removes everything |
| 11 | Privacy | Open the policy from the footer | Each promise has a test (design section 12B) |

## Two things to say out loud

- In live mode the same pages call Groq (Studio) and Langflow (Chat). Live chat stays off until `LANGFLOW_PER_USER_TOOLS=1`
  is set, which is the operator confirming the flow's tools read the learner's own words.
- Practice results are shown and forgotten. The design leaves out spaced repetition on purpose.

## Automated version

With the stack up (or `make dev-api` and `make dev-web`) and a browser installed once:

```
cd web && npx playwright install chromium
E2E_BASE_URL=http://localhost:8080 npx playwright test e2e/library-practice.spec.ts
```

`make e2e` runs the whole browser suite. Two older browser tests only make sense against the nginx build on port 8080: the CSP headers (the Vite dev server
sends none) and "no white flash" (it blocks `/assets/*.js`, which the dev server does not use). Run against the dev server, those two fail for that reason, not because of a bug.
