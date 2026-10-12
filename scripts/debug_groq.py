import json, sys, urllib.request, os
sys.path.insert(0, "/app/custom_components")
from tutor_core import db as tc_db, prompts as tc_prompts, vocab as tc_vocab

# Shows the raw Groq choice for one learner's English words. Usage: TUTOR_DEV_USER_ID=<learner id> python debug_groq.py
learner_id = int(os.environ.get("TUTOR_DEV_USER_ID") or sys.exit("Set TUTOR_DEV_USER_ID to the learner whose English words to use."))
conn = tc_db.connect()
words = ", ".join(tc_vocab.load_words(conn, learner_id, "en"))
conn.close()
if not words:
    sys.exit(f"Learner {learner_id} has no English words yet.")
prompt = tc_prompts.build_story_prompt("English", words, "narration")

payload = {"model": "openai/gpt-oss-20b",
           "messages": [{"role": "user", "content": prompt}],
           "max_tokens": 400}
req = urllib.request.Request(
    "https://api.groq.com/openai/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
             "Content-Type": "application/json",
             "User-Agent": "language-tutor-story-tool/1.0"})
body = json.loads(urllib.request.urlopen(req, timeout=30).read())
print(json.dumps(body["choices"][0], indent=2)[:2500])
print(body.get("usage"))