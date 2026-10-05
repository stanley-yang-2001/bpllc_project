import json, sys, urllib.request, os
sys.path.insert(0, "/app/custom_components")
import story_tool

conn = story_tool.get_connection()
words = story_tool.load_words(conn)
conn.close()
prompt = story_tool.build_story_prompt("English", words, "narration")

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