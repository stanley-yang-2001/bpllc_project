# Use the model the learner chooses (design, 22 October 2026)

**Status: design only. Nothing is built. Section 6 lists the decisions I need from you before I start.**

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
**Storage (migration 0010, table `tutor.user_models`, one row per learner):** `model`, `base_url`, `api_key_encrypted`, `key_last4`, `updated_at`. The key is encrypted with a server secret (`MODEL_KEY_SECRET` in `.env`, Fernet). It is **never returned by any API**: the Settings page shows only "key ending 1a2b" and a Replace button. Deleting the account deletes the row (cascade), and a Remove button deletes it at any time.

**Settings page:** a "My model" card with the three fields, a **Test** button (sends one tiny request, shows success or the provider's error), Save, Remove. Nine languages in the message table, as for every other string.

**Stories (phase 1):** when the learner has a saved model, `POST /api/stories/generate` builds a `call_fn` for their endpoint and passes it as `call_groq_fn`. Everything after the call is unchanged, including the stray-word check and quality report, and the report says which model wrote the story. Request differences: no `reasoning_effort` unless the model is known to take it (other providers reject unknown fields), and `max_tokens` is sent as `max_tokens`.

**Chat (phase 2):** the Agent's model is a node in the shared flow. Langflow takes per-request overrides ("tweaks"), which the project already uses for the learner id. Phase 2 passes the learner's model, key and address as tweaks on a chat request. This must be **proved on your machine first** with a spike like M0 (does the Agent node accept an OpenAI-compatible override per request, and does the key stay out of Langflow's logs and stored chat?). The chat story tool would call back through the same endpoint. I will not promise phase 2 until the spike passes.

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

## 7. Build order once decided
1. Migration 0010 and the encryption helper, with tests (round trip, key never in any response, cascade delete).
2. The address guard (SSRF rules) with tests for each refused class.
3. The `call_fn` for an OpenAI-compatible endpoint, tested against a fake server, and Test / Save / Remove routes.
4. The Settings card, nine languages.
5. Story Studio uses it; the quality report names the model.
6. The privacy policy sentence and version bump.
7. The phase 2 spike on your machine.
