# Privacy policy: options for you to approve

**Status: DRAFT (5 November 2026), except one change made on the owner's instruction on 9 November 2026: the English policy (version `2026-11-09`) now has a row for practice progress and answer times, and the deletion and download lists mention them (topic 1 below, in part). Everything else here is not live.** The approved English copy (`api/app/policy/en.json`, version `2026-10-24`, approved by the project owner) and `POLICY_VERSION` are untouched. This file only lists where the approved wording no longer matches what the app does, and offers wording for each place. Pick an option per topic (or write your own), and I will make the change you approve.

I am not a lawyer. The wording below states what the code does; whether it meets the rules where your learners live (for example the EU/UK GDPR or California law) is for you, or someone you ask, to judge.

## 1. What changed since 24 October

Everything in this table is checked against the code, not remembered. "Where" is the file that does it.

| # | The approved copy says | The app now does | Where |
|---|---|---|---|
| 1 | Section 2 lists what is stored. Practice is not mentioned. | Practice is remembered per word (box 1 to 5, next due time, right and wrong counts, last answered) and per day (how many answers, for the streak). It is in "Download my data" and is removed with the account (cascade). | `migrations/0014_word_progress.py`, `services/export.py`, `services/progress.py` |
| 2 | Section 5, "AI features": chat, and the words Story Studio uses, go to Groq. | Four more features send text to the AI service: **Write missing meanings** (your words), **Label parts of speech** (your words), **Translate** (the words or story lines you pick; shown, never stored) and **Pronunciation** for languages that are not Chinese, Japanese or Korean (the text you pick; shown, never stored). Meanings and labels are saved on the word. | `services/meanings.py`, `services/pos_labels.py`, `services/text_tools.py` |
| 3 | Section 5, "Your own AI model": your words and story requests go to your provider. | With a model of your own, **all** of the above go to your provider instead of Groq, and **chat too** if the operator has switched `CHAT_OWN_MODEL` on (messages, and the words the story tool reads). If your model fails you see an error that says why (your key removed from it); the shared service does not answer in its place. The key never leaves our server: the tutor service is given a one-turn throwaway code, not the key. | `services/ai_runner.py`, `routes/internal_model.py`, `services/chat_model.py` |
| 4 | Section 6 lists what deleting an account removes: name, email, password hash, words, languages, saved stories, preferences, chat history, sign-in records. | Also removed: practice progress and the settings and key of your own model (both cascade from the account). The list does not say so. | `migrations/0011`, `0014`, `routes/account.py` |
| 5 | Section 4: "Nothing else about you is kept in the browser." | The voice you pick for reading aloud, per language, is kept in this browser's local storage (`tutor.voice.<language>`). It is not wiped on sign-out (the theme copy is). It holds a voice name such as "Microsoft Sabina", not your account. | `web/src/speech/speak.ts` |
| 6 | Not mentioned. | Reading aloud and dictation use the voices built into your browser or device. Some browsers offer "online" voices, and then the text being read goes to the browser's maker. The app does not choose or see that. | `web/src/speech/` |

Things that did **not** change and need no wording: one cookie only (checked: the only `set_cookie` is the sign-in cookie), no analytics, name and email never sent to an AI service, chats stored in the tutor service and deleted with the account, saved stories, the download file (it now also lists practice progress).

## 2. Options, topic by topic

The wording follows the policy's own style (short, "you", bold lead-ins). The text in quotes is what would be added or changed.

### Topic 1: practice progress (section 2 table, one new row)

- **1A (recommended).** New row, after "Words, meanings and stories you add":
  > **Your practice progress** | For each word you practise: which box it is in, when it is next due, how many times you were right and wrong, and when you last answered. For each day, how many answers you gave (for your streak). Used only to choose what to practise next and to show your progress. Part of your download; removed when you delete your account.
- **1B (shorter).** The same row without the second sentence about the streak: *"For each word you practise: its box, when it is next due, and how many times you were right and wrong. Used to choose what to practise next."* Shorter, but "streak" data (a count of answers per day) is then not mentioned although it is stored.

### Topic 2: the AI features (section 5, first bullet)

- **2A (recommended): one sentence naming the features, one sentence saying what is kept.** Replace the first bullet with:
  > **AI features.** Chat, Story Studio, "Write missing meanings", "Label parts of speech", translations and pronunciations ask an AI service (Groq) to write the answer. For that, the text it needs is sent: what you type in Chat and the replies; the words from your list that Story Studio uses (a random selection if your list is long), with the kind, topic and difficulty you pick; the words a meaning or a part-of-speech label is written for; or the words and lines you ask to have translated or pronounced. Your name and email address are **not** sent. Meanings and labels are saved on the word. A story you do not save, a translation and a pronunciation are not kept by the app.
- **2B: a small table** (feature, what is sent, what is kept) inside section 5. Clearer to scan, longer, and the table has to be kept in step every time a feature is added. I would pick it only if you expect more AI features soon.
- **2C: keep the first bullet as it is** and accept that it names two of six features. Not recommended: a learner who presses "Write missing meanings" has not been told that their words go to Groq.

### Topic 3: your own AI model (section 5, second bullet)

- **3A (recommended).** Replace the second bullet with:
  > **Your own AI model.** If the operator switches it on for your account and you set it up, the AI features above ask **your** provider instead of Groq, and so do your Chat messages if the operator has also allowed that. Everything listed above for those features is then sent to the provider you name, which has its own privacy rules that this policy does not cover. Your API key is stored encrypted on our server and used only by our server to call your provider; it is not given to the tutor service and is never shown again. If your provider cannot answer, you see its reason (with your key removed) and the shared service does not answer instead. Nothing is sent to your provider unless you set it up, and you can remove the model and key in Settings, My model.
- **3B (shorter).** *"If you set up your own AI model, the AI features above (including Chat, if the operator allows it) ask your provider instead of Groq, with the same text. That provider has its own privacy rules, which this policy does not cover. Your API key is stored encrypted and is never shown again. Nothing is sent to it unless you set it up."* Drops the "key stays on our server" and "no fallback" statements; both are true and are facts a careful reader may want.

### Topic 4: what deletion removes (section 6)

- **4A (recommended).** In the first sentence, change the list to: *"... your name, email, password hash, words, **practice progress**, languages, saved stories, display preferences, **your own model's settings and key**, chat history and sign-in records ..."*
- **4B.** Leave the list and add *"and everything else the app holds about you"*. Shorter, but it is a catch-all for a list that already names every item; a reader cannot check it.

### Topic 5: the voice choice kept in the browser (section 4)

- **5A (recommended: say it).** Add to the second paragraph: *"The voice you pick for reading aloud is also remembered in your browser, on that device only."*
- **5B (change the code, then no wording).** I make sign-out remove the voice choice as it removes the theme copy; section 4 stays true as written. Cost: after each sign-in you pick the voice again on that device. A voice name is not personal data, so I would not do this only for the policy.
- **5C.** Neither. The sentence "Nothing else about you is kept in the browser" would then be slightly untrue.

### Topic 6: browser voices (section 5, new bullet)

- **6A (recommended).** Add a bullet:
  > **Reading aloud.** Reading aloud and dictation use the voices of your browser or device. Some browsers offer online voices; if you pick one, the text being read is sent to the browser's maker. The app does not control that. Voices marked as local stay on your device.
  The last sentence depends on the browser marking a voice as local (`localService`) and on that mark being honest; I have not checked it in every browser, so drop it if you want only what is certain.
- **6B.** Leave it out. The app sends nothing; the browser does. Some policies still say so, because the learner may not know.

### Topic 7 (optional): the "In short" box

The box has three items. A fourth would put the biggest change where people actually read:
> *Words and messages you send to an AI feature go to an AI service (or to the model you set up yourself), never with your name or email. See section 5.*

Leave the box alone if you prefer it short; the sections already say it.

## 3. Decisions that are yours, not wording

1. **The version.** Any change that matters bumps `POLICY_VERSION` (today `2026-10-24`). The rule in `api/app/policy/__init__.py`: a copy is shown only if it is approved **and** its version equals `POLICY_VERSION`. So the moment the version moves, every other-language copy is withdrawn (English is shown, with a notice) until it is updated and approved again. Today only English is approved, so nothing visible is lost.
2. **People who already have an account.** The app records the version someone accepted at sign-up and has no way to ask existing learners to accept a new one (`privacy_version` is written once, in `services/users.py`). If you want existing learners to accept the new text, that is a feature to build (a banner, then a stored acceptance). Say so and I will propose it separately; I have not started it.
3. **Operator details.** Section 1 and section 12 use the operator's contact. Nothing in this draft changes them.
4. **What I did not check.** Groq's own retention and training terms; what your hosting or backups keep (section 6 already says to ask the operator); what any browser's online voices do. The wording above says only what the app does.

## 4. What I do after you choose

1. Edit `api/app/policy/en.json` (the sections named above) and nothing else in it that you did not pick.
2. Set `POLICY_VERSION` to the date you approve, and set `approved_on` and `approved_by` in `en.json` to what you tell me (I will not invent an approval).
3. Update `web/src/routes/Privacy.test.tsx` (it lists phrases the page must contain) and `api/tests/test_policy.py` if they depend on the version.
4. For 5B only: change the sign-out code and its test.
5. Deliver it as one patch, with the board and the "To do task" doc updated.

Reply with something like "1A, 2A, 3A, 4A, 5A, 6A, yes to the box, version 2026-11-xx", or tell me what to change.
