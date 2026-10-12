"""
Who Am I (spike) — milestone M0, throwaway.

Purpose: settle, before any Chat code is written, whether Langflow can hand a per-request
learner id to a tool through `tweaks`, while the Agent cannot see or change it (design section 3D,
"Plan A"). This component does nothing else: it reports what it received.

NAME THE HIDDEN INPUT `learner_id`, NEVER `user_id`. Langflow gives every component a read-only `user_id` property
that returns the id of the Langflow ACCOUNT running the flow (the owner of the API key), and it shadows an input of
that name: the first spike run saw the account's UUID instead of the id we sent, while `language` arrived fine.
SEND THE ID AS A STRING: Langflow's text-field handling accepts only a string, a list or a Data object and silently
drops anything else, so an integer tweak never arrives (the tool then sees NONE and, by design, refuses to act).
Other names Langflow reserves on a component: trace_name, graph, flow_id, flow_name, tracing_service, tree,
template_config, enabled_tools, ctx.

Inputs
  * `note`      — the ONLY tool-mode input, so the only argument the Agent can fill in (ignored).
  * `learner_id` — hidden (tool_mode off, advanced): set per request through tweaks.
  * `language`  — hidden, same.

It also reports the session id as the running graph sees it (Plan B: "the tool reads the session
id from the flow"), and holds for HOLD_SECONDS so that calls from different users genuinely
overlap in time: sequential success proves nothing about isolation.

Output (one line, parsed by scripts/spike_tweaks.py):
  WHOAMI learner_id=17 language=es langflow_user=<uuid> session=u17-ab12.. graph_session=.. t0=.. t1=.. thread=..

Fail closed: with no learner id the output says `learner_id=NONE` and nothing else is touched.
`TUTOR_DEV_USER_ID` (developer-only, set on the Langflow container) is reported as DEV(<id>).

Delete this file and its node once M0 is decided (record the result in CHANGELOG.md).
"""

import os
import re
import threading
import time

from langflow.custom import Component
from langflow.io import MessageTextInput, Output, StrInput
from langflow.schema.message import Message

HOLD_SECONDS = 1.5


def _clean(value) -> str:
    """One token with no spaces, so the line is trivial to parse."""
    text = re.sub(r"[^\w.:()\-]", "_", str(value).strip())
    return text or "NONE"


def _probe(getter):
    """Read something that may not exist, or may raise, in this Langflow version."""
    try:
        value = getter()
    except Exception:  # noqa: BLE001 - a probe: any failure just means "not available"
        return "UNAVAILABLE"
    return "NONE" if value in (None, "") else value


class SpikeWhoAmI(Component):
    display_name = "Who Am I (spike)"
    description = (
        "Spike: reports the user id and language this tool call received. Enable Tool Mode and "
        "attach to the Agent. Call it when the user asks who they are."
    )
    icon = "User"
    name = "SpikeWhoAmI"

    inputs = [
        MessageTextInput(
            name="note",
            display_name="Note",
            info="Anything; ignored. The Agent fills this in.",
            tool_mode=True,
        ),
        StrInput(
            name="learner_id",
            display_name="Learner ID (hidden)",
            info="Set per request through tweaks. The Agent never sees this field.",
            value="",
            advanced=True,
            tool_mode=False,
        ),
        StrInput(
            name="language",
            display_name="Language (hidden)",
            info="Set per request through tweaks. The Agent never sees this field.",
            value="",
            advanced=True,
            tool_mode=False,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run"),
    ]

    def run(self) -> Message:
        t0 = time.time()
        time.sleep(HOLD_SECONDS)  # make calls from different users overlap
        t1 = time.time()

        learner_id = str(self.learner_id or "").strip()
        if not learner_id:
            dev = os.environ.get("TUTOR_DEV_USER_ID", "").strip()
            learner_id = f"DEV({dev})" if dev else "NONE"
        langflow_user = _probe(lambda: self.user_id)      # the built-in property: the Langflow account, not a learner

        graph_session = _probe(lambda: self.graph.session_id)
        own_session = _probe(lambda: self.session_id)

        text = (
            f"WHOAMI learner_id={_clean(learner_id)} language={_clean(self.language or 'NONE')}"
            f" langflow_user={_clean(langflow_user)} session={_clean(own_session)} graph_session={_clean(graph_session)}"
            f" t0={t0:.3f} t1={t1:.3f} thread={threading.get_ident()}"
        )
        message = Message(text=text)
        self.status = message
        return message
