# Learning Objectives — Building a Language Tutor with Langflow

Based on the tutorial referenced in the roadmap: https://www.datacamp.com/tutorial/langflow

By the end of this project, you should be able to:

1. **Explain Langflow's component model** — describe how a low-code workflow is built from
   nodes that take typed inputs, perform one action, and pass outputs to the next node, and
   when a built-in component is enough versus when you need a custom one.

2. **Stand up a local Langflow + Postgres environment** — use Docker and Docker Compose to run
   Langflow and a linked Postgres database locally, without relying on any hosted service.

3. **Build a custom Python component in Langflow** — define a component class with typed
   `inputs` and an `outputs` method, and understand how that component becomes usable on the
   canvas.

4. **Read from and write to Postgres from a component** — use `psycopg2` inside a Langflow
   component to create a table if missing, bulk-insert records, and query existing rows.

5. **Configure an Agent node's tools and explain tool-calling** — attach one or more components
   to an Agent in "tool mode," and explain how the underlying LLM decides which tool (if any)
   to invoke based on a natural-language message and each tool's description.

6. **Design a small multi-agent system** — wire an orchestrating agent to call a specialized
   sub-agent as one of its own tools (here: a top-level routing agent calling a dedicated
   story-generation agent), rather than building everything into a single agent.

   > **Implementation note:** the story generator was first built as a sub-agent pipeline (the
   > Step 8 canvas components), then consolidated into a single tool component
   > (`story_tool.py`) because Tool Mode returns only a component's own output. The objective is
   > still met through the orchestrator-plus-tools design; the story call is now a direct Groq
   > request rather than a second Agent node. See `IMPLEMENTATION-GUIDE.md`, Step 8.

7. **Write and iterate on a constrained prompt template** — build a Prompt component that
   injects variables (e.g. `{language}`, `{words}`) into an instruction that limits the LLM's
   output to a fixed vocabulary, and refine it based on how well the model actually respects
   the constraint.

8. **Swap an agent's model provider and reason about the trade-offs** — replace a paid, hosted
   model (e.g. OpenAI GPT) with a free, open-source model served locally via Ollama (or a
   hosted free-tier alternative like Hugging Face Inference), and explain the resulting
   trade-offs in cost, latency, and output quality/consistency.

   > **Implementation note:** this project uses Groq's free tier (`openai/gpt-oss-20b` and
   > `openai/gpt-oss-120b`) rather than Ollama or Hugging Face, because local hardware couldn't
   > run a model comfortably. The trade-off to reason about now also includes free-tier rate
   > limits and, most importantly, agentic instruction-following: smaller open-weight models
   > are less reliable at relaying a tool's output unchanged. See `CHANGELOG.md` and
   > `DEVELOPER-DIARY.md`.
