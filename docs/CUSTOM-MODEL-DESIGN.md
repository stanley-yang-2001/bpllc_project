# Use the model the learner chooses (design, 22 October 2026)

**Status (1 November 2026): phase 1 (stories) is built and tested here, not yet run on your machine; decisions are in section 6. Phase 2 (chat) is not built: the spike that decides how is written and tested against fakes (section 9), and waits for you to run it. Not done: the privacy-policy sentence (it needs your wording and a version bump, which makes every learner accept the policy again).**

## 1. The request
A learner can enter **a model name, an API key and the model's address** (base URL), and the site then uses that model instead of the shared Groq one.

## 2. Where a model is called today
| Place | How | Code |
|---|---|---|
| Story Studio and the chat story tool | one HTTP call to Groq's OpenAI-style `/chat/completions`, key from `GROQ_API_KEY`, model from `GROQ_MODEL` (default `openai/gpt-oss-120b`), with `reasoning_effort: low` and `max_tokens 1500` | `tutor_core/groq.py: call_groq(prompt)` |
| Chat (the Agent that decides which tool to call) | Langflow's Groq model node inside `flows/language-tutor.json`, key from the container's `GROQ_API_KEY` | the flow |
| Health check | a light call to Groq's models list | `api/app/services/story_llm.py` |
The story pipeline already takes the model call as a function (`call_groq_fn`), so a learner's model fits there without changing the pipeline.

## 3. Proposal: an "OpenAI-compatible endpoint" per learner
Almost every provider (OpenAI, Groq, Together, OpenRouter, Ollama, LM Studio, vLLM, Azure OpenAI's compatible route) speaks the same `/chat/completions` request. So the learner enters exactly the three things asked for:
- **Model name** (for example `gpt-4o-mini` or `llama3.1`),
- **API key** (optional for a local server),
- **Model address**: the base URL, for example `https://api.openai.com/v1`; we add `/chat/completions`.
A provider that is not OpenAI-compatible (Anthropic's own API, Gemini's own API) would need its own adapter; I would add those later only if you want them.

## 4. How it works
**Storage (migration 0011, table `tutor.user_models` (0010 is the chat-language preference), one row per learner):** `model`, `base_url`, `api_key_encrypted`, `key_last4`, `updated_at`. The key is encrypted with a server secret (`MODEL_KEY_SECRET` in `.env`, Fernet). It is **never returned by any API**: the Settings page shows only "key ending 1a2b" and a Replace button. Deleting the account deletes the row (cascade), and a Remove button deletes it at any time.

**Settings page:** a "My model" card with the three fields, a **Test** button (sends one tiny request, shows success or the provider's error), Save, Remove. Nine languages in the message table, as for every other string.

**Stories (phase 1):** when the learner has a saved model, `POST /api/stories/generate` builds a `call_fn` for their endpoint and passes it as `call_groq_fn`. Everything after the call is unchanged, including the stray-word check and quality report, and the report says which model wrote the story. Request differences: no `reasoning_effort` unless the model is known to take it (other providers reject unknown fields), and `max_tokens` is sent as `max_tokens`.

**Chat (phase 2):** the Agent's model is a node in the shared flow. Langflow takes per-request overrides ("tweaks"), which the project already uses for the learner id. Phase 2 passes the learner's model, key and address as tweaks on a chat request. This must be **proved on your machine first** with a spike like M0 (section 9 has it and what Langflow's own source says) (does the Agent node accept an OpenAI-compatible override per request, and does the key stay out of Langflow's logs and stored chat?). The chat story tool would call back through the same endpoint. I will not promise phase 2 until the spike passes.

## 5. Risks and how the design handles them
1. **The server calls an address the learner typed (SSRF).** Without a guard, someone could point it at the database, Langflow, or the host's cloud metadata address. Rule: https only; resolve the name and refuse loopback, private, link-local and metadata addresses; no redirects; 30 second timeout; response size cap. Local models (Ollama on the learner's own PC) are refused by default because the server cannot reach that PC anyway; an `ALLOW_PRIVATE_MODEL_URLS=1` switch exists for a single-user setup like yours.
2. **Key leakage.** Encrypted at rest, never in logs, errors, health output, chat history or the quality report; request errors are shown with the key removed. The key crosses the network only when the learner saves it (site over HTTPS) and when we call their provider.
3. **Quality.** Step 10 measured only `openai/gpt-oss-120b`. Another model may ignore the word list or the format. The same quality check runs on every story, so the report shows it, and the Settings card says "results vary by model".
4. **Cost and limits.** The learner's own key pays their own provider, so the shared tokens-per-minute budget should not be charged to them (the AI gate still limits simultaneous calls per learner). Open question 4.
5. **Privacy.** Their words and prompts go to a third party they chose. The privacy policy copy needs a new sentence and a new version (the site already has a versioned policy flow, 8d).
6. **Abuse.** Rate limit the Test button; cap field lengths; reject URLs with credentials in them.

## 6. Decisions for you
1. **Scope:** stories only first (phase 1), then chat after the spike (phase 2)? *(my recommendation: yes)*
2. **Who can use it:** every account, or only accounts you switch on (an `AI_CUSTOM_MODEL_ENABLED` flag, off by default)? *(recommendation: a flag, off by default, because of risk 1)*
3. **Local models:** keep refusing private addresses by default, with your single-user override? *(recommendation: yes)*
4. **Limits:** should a learner on their own key skip the shared token budget? *(recommendation: yes, with a per-learner request limit)*
5. **Providers:** OpenAI-compatible only for now? *(recommendation: yes)*
6. **Fallback:** if their model fails, show the error, or quietly use the shared Groq model? *(recommendation: show the error; a silent fallback would send their words somewhere they did not choose)*

### Decisions (24 October 2026, from the owner)
1. Yes: stories first (phase 1), chat after the spike (phase 2).
2. Only accounts that have the custom model switched on (a per-account flag, off by default), not one global setting for everyone.
3. Yes: private addresses stay refused by default, with the single-user override.
4. Yes: a learner on their own key skips the shared token budget, with a per-learner request limit.
5. Yes: OpenAI-compatible providers only for now.
6. If their model fails, show the error and recommend switching back to the shared Groq model; never fall back silently.

## 7. Build order once decided
1. Migration 0011 and the encryption helper, with tests (round trip, key never in any response, cascade delete).
2. The address guard (SSRF rules) with tests for each refused class.
3. The `call_fn` for an OpenAI-compatible endpoint, tested against a fake server, and Test / Save / Remove routes.
4. The Settings card, nine languages.
5. Story Studio uses it; the quality report names the model.
6. The privacy policy sentence and version bump.
7. The phase 2 spike on your machine.


## 8. What was built in phase 1 (24 October 2026)
- Migration 0011: `tutor.users.custom_model_enabled` (off for everyone) and `tutor.user_models` (model, base URL, encrypted key, last four characters). The row goes with the account and is in "Download my data" without the key.
- Switch an account on: `docker compose exec api python -m app.custom_model_admin on you@example.com` (also `off`, `list`). Needs `MODEL_KEY_SECRET` in `.env`; empty means the feature is off for everyone. `ALLOW_PRIVATE_MODEL_URLS=1` allows a local address (your own machine only).
- Address guard: https only, no credentials or query in the address, every address the name resolves to must be public, the call goes to the address that was checked, no redirects, 30 second timeout, 1 MB answer cap, errors shown with the key removed.
- Routes: `GET/PUT/DELETE /api/me/model` and `POST /api/me/model/test` (5 tests a minute). Story Studio uses the model when it is saved: no shared token budget, 10 stories a minute, a failure shows the provider's reason and says to remove the model to go back to the shared one; no silent fallback. The report names the model.
- Settings has a My model card (only on switched-on accounts), in nine languages.
- Not built: chat on your own model (phase 2), a saved story remembering which model wrote it, other providers than OpenAI-compatible.

## 9. Phase 2 (chat): the spike, and what Langflow's source says (1 November 2026)
**Status: `scripts/spike_model_tweaks.py` is written and tested against fakes (including a real Postgres for the storage search). It has not been run on your machine. Nothing in the real flow changed: the Groq component gained an optional "Base URL" field (empty means Groq, so the repo's flow behaves exactly as before) and `flows/language-tutor.json` is untouched until the spike passes.**

### 9.1 What Langflow 1.12.2 does (read from the `langflow-base` and `lfx` 1.12.2 packages, the version the Dockerfile pins; not yet confirmed on a run)
1. A tweak sets a field of a node, found by node id or display name. A **string** is stored as the field's value and the field's "load from database" flag is turned off, so a key sent as a tweak is used as typed and is not looked up as the name of a stored variable.
2. A tweak for a field the node does not have is **skipped without any error**. That is why the model node needs the new Base URL field, and why old node code shows up as "the fake model was never called".
3. Only code fields (and two SQL fields) are protected. A deployment setting, `LANGFLOW_TWEAKS_POLICY` (`permissive` by default; `declared` and `off` refuse tweaks), can answer 422 "does not accept tweaks". Only the account that owns the flow may send tweaks; anyone else gets 404. The spike explains both when it meets them.
4. Langflow records each run: chat messages, one "transaction" per component and one "vertex build" per component. The transaction log masks values of keys called `api_key`, `password` and the like to their **first four and last four characters**. Whether the whole key also lands in another table is what the spike's `stored_key` check measures; the source cannot answer it.
5. The warm graph cache (`LANGFLOW_WARM_REGISTRY_ENABLED`, off by default) is skipped when a request carries tweaks.

### 9.2 What the spike checks (inside the Langflow container; it starts a tiny OpenAI-compatible server of its own, so it needs no second provider and costs nothing)
| Check | Passes when |
|---|---|
| `override` | the model call reaches the fake server with the tweaked model name, the tweaked key as `Authorization: Bearer ...`, at `/chat/completions`, and the Agent's reply is the fake model's sentence |
| `parallel`, `overlap` | several learners at the same moment each reach the server with their own pair, never another's; calls that did not overlap in time are INCONCLUSIVE, not PASS |
| `control` | a request with no tweaks, sent after the overrides, goes to the shared Groq model and not to the fake one (an override must not stick; this is the one case where Langflow's source mentions a cached graph) |
| `no_leak` | no throwaway key appears in anything Langflow returned |
| `stored_key` | reported next to the verdict: FAIL if the whole key is found in Langflow's database or message store, PASS if only the masked form or nothing is, INCONCLUSIVE if it could not look |
| `real_provider` (optional) | your real provider's model, set through the same tweaks, drives the Agent's calculator tool (a model without tool-call support shows as INCONCLUSIVE or ERROR) |

The throwaway keys are invented by the script (`spike-key-...`). Your real key is only ever sent by `--real-model`, is read from the environment variable `SPIKE_REAL_API_KEY`, is never printed or saved, and is not searched for in the database (use a key you can revoke afterwards).

### 9.3 Two ways to build phase 2
- **Option A, tweaks carry model, key and address.** Simple, and the spike decides whether it works. Two costs even when it works. (1) Langflow keeps at least the masked key (eight characters) in its transaction log, and maybe more. (2) The address guard of phase 1 resolves the name and calls the address it checked; with tweaks, Langflow resolves the name again itself, so the guard can only check, not pin, and a name that changes its answer between the check and the call defeats it.
- **Option B, the API is the model (recommended if `stored_key` FAILs, and a good idea even if not).** The API gets an internal OpenAI-compatible route that only the Langflow container can reach. For a chat request the API issues a random one-time token that stands for this learner and this request (minutes to live) and sends Langflow tweaks of: the learner's model name, the API's internal address as Base URL, and the token as the key. The API receives Langflow's model request, looks up the learner's stored encrypted key, runs the **same address guard with the address pinned**, forwards the request (streamed) and counts the per-learner request limit. The real key never leaves the API, Langflow stores only a throwaway token, the guard is the code phase 1 already has, and the provider's error reaches the learner in the same words as in Story Studio. Cost: one internal route with streaming pass-through, a token store, and tests; the route must not be published outside the Docker network.
- **Either way, one gap remains:** the Story Generator Tool inside the chat flow calls Groq itself with the shared key (`tutor_core.tools.story_for_agent`), so a story made in chat would still be written by the shared model while the Agent's own sentences come from the learner's. Phase 2 must also give that tool the learner's endpoint (with option B: the same token and internal address as two more hidden inputs).

### 9.4 Run it on your machine (Windows, in the project folder)
1. Run the free checks. One command: `--create-flow` makes the spike's own copy of the flow by itself ("language tutor spike", endpoint `language-tutor-spike`: the repo flow with the Groq node brought up to the current `custom_components/groq_language_model.py`, so it has the advanced "Base URL" field; the real "language tutor" flow is not touched). A copy that already exists is reused, so the same command works every time; if you made a copy by hand earlier, delete it in Langflow first. The key defaults to the node id `GroqLanguageModel-h5DsK`.
```
docker compose exec langflow python /app/scripts/spike_model_tweaks.py --create-flow
```
It takes about a minute and one Groq turn (the `control` check; add `--skip-control` to avoid it, and wait a minute and re-run if it says rate limit). A line `ERROR ... Flow identifier ... not found` means the copy does not exist: add `--create-flow`. A report where `no_leak` and `stored_key` say INCONCLUSIVE "nothing was tested" means no request carrying a key got through; read the ERROR lines above them.
2. Look for the key in Langflow's log, a second source the script cannot read:
```
docker compose logs langflow | findstr /C:"spike-key-"
```
No line should come out. If one does, paste it (it is a throwaway key).
3. Optional, your real provider (use a key you can revoke afterwards). Put the key in the environment of your command window, not in the command (the `-e` below copies it from there):
```
set SPIKE_REAL_API_KEY=your-key
docker compose exec -e SPIKE_REAL_API_KEY langflow python /app/scripts/spike_model_tweaks.py --skip-control --real-model gpt-4o-mini --real-base-url https://api.openai.com/v1
```
Paste the printed report back. The script saves `scripts/spike_model_tweaks_<time>.json` (git-ignored; keys cut to their last four characters).

### 9.5 Result of the spike on your machine (2 November 2026)
Run with `--create-flow` against Langflow 1.12.2 and the repo's flow: `override` PASS (the call arrived with the tweaked model name, key and address, and the Agent answered with that model's reply), `parallel` PASS (three learners at once, each with their own pair; `overlap` PASS, so the calls really ran at the same time), `control` PASS (a request without tweaks went to the shared Groq model, so an override does not stick), `no_leak` PASS, `stored_key` PASS (neither the whole key nor its masked "abcd...wxyz" form was found in Langflow's database or message store).
So **option A (tweaks carry model, key and address) works** on this Langflow version. Not yet shown, in order of importance:
1. The database search ran immediately after the answers, and Langflow writes some records a moment later; the script now waits 8 seconds (`--settle`) first. Re-run once and check that `stored_key` still passes, and that `docker compose logs langflow | findstr /C:"spike-key-"` prints nothing.
2. That your real provider's model can drive the Agent's tools (`--real-model`, step 3 above).
3. The two costs of option A in section 9.3 stay: the address guard can check but not pin the address, and the Story Generator Tool inside the chat flow still calls the shared model. Option B removes both and is still the safer build; the choice is yours once 1 and 2 are done.
