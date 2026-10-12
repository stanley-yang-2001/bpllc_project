# Captured Langflow responses

Real responses from a running Langflow 1.12.2, used to test `app/services/langflow_client.py` against what Langflow actually
returns rather than what we assume it returns.

| file | what it is | how it was made |
|---|---|---|
| `whoami_run.json` | the run response of the "Who Am I (spike)" tool called through the Agent, for learner 101 | the third live M0 spike run (`scripts/spike_tweaks.py`), the `raw` entry for user 101. One edit: the Langflow account UUID in the tool's report was replaced with zeros |

Facts this real response established: the reply text is at `outputs[0].outputs[0].results.message.text`; the tool call appears twice
(under `message.content_blocks` and `message.data.content_blocks`) and must be counted once; and Langflow reports the tool by its
snake_case name (`spike_who_am_i`), not its display name.

Still to capture with `scripts/capture_fixtures.py` (the tests that need them skip until the files exist): `greeting_run.json`,
`story_run.json`, `story_messages.json`.
