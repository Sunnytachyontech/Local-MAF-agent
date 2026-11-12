# Local MAF Agent

A small Microsoft Agent Framework (MAF) agent that answers HR questions about
hire types, running entirely locally against a Foundry Local model.

The agent exposes one tool, `lookup_hire_type`, backed by `hire_types.json`,
and is instructed never to answer from memory.

## Setup

```powershell
py -3.14 -m venv taketwo
.\taketwo\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
```

## Run

```powershell
python demo_agent.py
```

Then ask questions at the prompt, for example:

- `list out the hire types`
- `what is the notice period for Intern?`

Type `exit` to quit.

## Choosing a model

Set `FOUNDRY_LOCAL_MODEL` in `.env`. **Model choice is the single most
important setting here.**

`phi-4-mini` does not work for this agent. The Foundry Local catalog reports
`supports_tool_calling=True` for it, but in practice it writes the tool call
out as ordinary message text:

```
[{"name":"lookup_hire_type","parameters":{"properties":{"name":"all"}}}]
```

Note the `"properties"` wrapper -- the model is copying the JSON *schema* it
was shown instead of filling in an arguments object. The framework never
recognises this as a tool call, so the tool never runs and that raw string is
returned as the answer. Forcing `tool_choice="required"` does not help; the
native grammar path then fails with HTTP 500
`ThrowInvalidToolCallWithoutRecovery`.

Verified working models:

| Model | Size | Notes |
|---|---|---|
| `qwen3-4b` | 2.7 GB | Recommended. Smallest model that reliably calls tools. |
| `qwen2.5-7b` | 6.3 GB | Also works, roughly 2x slower on CPU. |

Treat the catalog's `supports_tool_calling` flag as necessary but not
sufficient. Verify by checking that the `[tool called] ...` line actually
prints when you ask a question -- that is the proof the tool executed.

## Performance

Foundry Local ships only `generic-cpu` builds for these models, so inference
is CPU-bound. Expect a minute or more per response. That is not a hang.
