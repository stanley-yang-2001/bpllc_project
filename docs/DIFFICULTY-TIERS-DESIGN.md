# Story difficulty tiers (design only, 23 October 2026)

Status: **not built.** The owner asked for a difficulty tier for stories with three measures. This note says what each
measure is, how it is counted, how a tier is picked, and what needs deciding. Nothing here changes behaviour yet.

## The three measures

| # | Measure | How it is counted | Needs |
|---|---|---|---|
| 1 | **Length of the story** | Words (or characters for Chinese and Japanese) and sentences or lines, counted from the finished story | nothing new; `tutor_core.quality` already counts units and words per unit |
| 2 | **Amount of the learner's vocabulary used** | How many different list words appear, and the share of the story's words that come from the list. English matches inflections today; other languages need the per-language word forms the vocabulary check does not have yet (the check is English-only) | per-language word matching (see "What is missing") |
| 3 | **Share of uncommon words** | The share of the story's words that are not in the language's list of everyday words (for example the 3,000 most frequent), not counting the learner's own list words and names | a word-frequency list for each of the nine languages |

## Tiers

Three tiers, each a set of targets for the three measures. The numbers below are **starting guesses** to be tuned on real stories
(the same way the stray-word limit was tuned), not decisions.

| Tier | Length | Own words used | Uncommon words |
|---|---|---|---|
| Easy | about 40 to 70 words, 4 to 6 lines | at least 60% of the story's words from the list, using at least 3 different list words | 0 to 5% |
| Medium | about 80 to 140 words | 30 to 60% of the words from the list, at least 5 different list words | 5 to 15% |
| Hard | about 150 to 250 words | up to 30% from the list, at least 8 different list words | 15 to 30% |

A learner with a short list cannot reach Medium or Hard on measure 2: the tier is limited by what the list allows, and Studio says so.

## How a tier is used

1. **Chosen in Story Studio** next to the kind and topic: "Easy", "Medium", "Hard" or "Any" (today's behaviour). The chat story tool gets an optional `difficulty` argument the same way it got `story_type`.
2. **In the prompt:** the tier sets the length rule and tells the model how much of the list to use and to keep other words everyday words. This reuses the existing length-rule slot of each story kind.
3. **In the quality report:** the finished story is measured on all three and shown as "Easy / Medium / Hard (what it measured as)" so a learner sees if the model hit the tier. A story that misses its tier is reported, not silently relabelled; whether it should be regenerated once is a decision below.
4. **In the Library:** the measured tier is stored with the story (one column on `tutor.stories`, a migration) so the Library can be filtered by it.

## What is missing before it can be built

- **A frequency list per language.** The usual source is the open-source `wordfreq` Python package (data for all nine languages; it adds some tens of MB to the API and Langflow images) or a smaller hand-picked everyday list per language. Chinese, Japanese and Korean need word splitting to use it, the same gap fill-in-the-blank had; the CJK method used there (match the learner's own words) does not give "uncommon" counts.
- **Per-language word matching** for measure 2 (inflections and particles), which the vocabulary check does not do for non-English today.
- **A measurement round** on your machine, as for languages: generate stories per tier and look at where the real numbers fall before fixing the table above.

## Decisions (owner, 23 October 2026)

1. **Chosen by the learner** in Story Studio (Any, Easy, Medium, Hard, or Custom).
2. **Frequency data:** a small everyday-word list, for **English, Spanish and French first**. German, Italian and Portuguese get one later.
3. **Chinese, Japanese and Korean:** measure length and own words used; **skip uncommon words** until a splitter exists. The splitter is built **after all the other tasks**.
4. **A story that misses its tier is shown as it is,** with the tier that was asked for next to what it measured. No regenerating for tier.
5. **The three tier sizes above are right.**
6. **The learner can customise the three elements** (length, own words used, uncommon share) instead of picking a preset. The page notes the limit: the model follows these targets loosely, especially own-word counts and the uncommon share, which is why the report shows what was measured.

## What is built (24 October 2026)

See the changelog entry of that date. Not built: German, Italian and Portuguese uncommon-word lists, the splitter, and a `difficulty` argument for the chat story tool.
