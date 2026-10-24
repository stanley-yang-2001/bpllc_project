# Environment settings (`.env`)

Docker Compose and the API read their settings from a file called `.env` in the project folder. It is git-ignored: never
commit real values. There is no template file; create `.env` and add the lines below. Only the three required ones must be
set; everything else has a default.

```
# --- required ---
GROQ_API_KEY=            # from the Groq console; Langflow's Groq node falls back to this
JWT_SECRET=              # at least 32 random characters, e.g.  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
TOOLS_DB_PASSWORD=       # password of the narrow database role the Langflow tools use (migration 0008). A long random one
                         # with NO : @ / % ? # or spaces (it goes into a URL), e.g.  python3 -c "import secrets; print(secrets.token_hex(24))"
                         # The API sets it on the role at startup. Compose refuses to start without it.
```

## Everything else (optional; the value shown is the default)

```
# --- database and Langflow admin (defaults are fine for local development) ------------------------
# POSTGRES_PASSWORD=langflow
# LANGFLOW_SUPERUSER_PASSWORD=admin123

# --- site -----------------------------------------------------------------------------------------
# AI_MODE=live                     # live | stub. "stub" = no Langflow or Groq needed: the chat answers from a fixed script
# COOKIE_SECURE=0                  # set to 1 behind HTTPS
# PRIVACY_CONTACT=                 # who learners can ask about their data; shown on the privacy page
# DEMO_EMAIL=demo@example.com
# DEMO_PASSWORD=

# --- chat (milestone M5) --------------------------------------------------------------------------
# Live chat refuses to run until the flow's tools read the learner's own words (milestones M0 and M3), because
# until then every learner would share one word list. Set LANGFLOW_PER_USER_TOOLS=1 only when that is true.
# LANGFLOW_PER_USER_TOOLS=0
# LANGFLOW_API_KEY=                # a Langflow API key (Langflow: Settings, API keys); required once the switch above is 1
# LANGFLOW_FLOW=language-tutor     # the flow's endpoint name
# LANGFLOW_TWEAK_KEYS=AddWord-WhP5g,StoryGeneratorTool-RQpvc    # node ids in flows/language-tutor.json (the style M0 verified); empty = send no tweaks (Plan B)
# AI_GATE_SLOTS=2                  # AI calls at once across all learners (Groq free tier)
# AI_TOKENS_PER_MINUTE=8000        # tokens the whole app may use in any 60 seconds (Groq free tier); 0 = no limit

# --- a learner's own model (docs/CUSTOM-MODEL-DESIGN.md) ---------------------------------------------
# MODEL_KEY_SECRET=                # a long random value (16+ characters) that encrypts learners' own API keys in the database. EMPTY = the feature is off for everyone. Changing it makes saved keys unreadable (learners enter them again).
# ALLOW_PRIVATE_MODEL_URLS=0       # 1 = a model address may be on your own network or http:// (a local Ollama). Single-user setups only: it lets the server call any address a learner types.
# Switch an account on (off by default), from the project folder:
#   docker compose exec api python -m app.custom_model_admin on you@example.com      (also: off, list)

# --- the Langflow tools (milestone M3) --------------------------------------------------------------
# GROQ_MODEL=openai/gpt-oss-120b   # the model Step 10 measured; change only with a new measurement
# MAX_PROMPT_WORDS=150             # at most this many of a learner's words go into one story prompt
# LANGFLOW_RUN_AS_USER=user        # the user the langflow base image runs as (see the comment in langflow/Dockerfile)
# TUTOR_DEV_USER_ID=               # DEVELOPMENT ONLY: acts as this learner when a request sends none. Keep EMPTY otherwise.
# TUTOR_DEV_LANGUAGE=en            # ... and this language
```
