# Created Is Not Verified

A file, skill, Claude session, Codex patch, model artifact, test harness, or green workflow is not correct merely because it exists.

## Evidence ladder

| State | What it proves | What it does not prove |
|---|---|---|
| `created` | An artifact was emitted | Syntax, behavior, integration, or value |
| `parses` | The interpreter can read it | Correct semantics |
| `unit_tested` | Selected isolated cases pass | Real inputs, integrations, or outcomes |
| `integrated` | Components connect in a named environment | Correct domain behavior |
| `executed` | An exact command ran against identified inputs | Generalization or profitability |
| `outcome_validated` | A predefined held-out or forward result met its gate | Permanent validity |
| `authorized` | A human approved the bounded use | Safety outside that authority envelope |

Promotion must move one step at a time. No model, agent, skill, chat, document, or test may promote itself.

## Source authority

Claude, Codex, ChatGPT, skills, and agent outputs are classified as one of:

- implementation candidate;
- hypothesis;
- design input;
- provenance;
- historical context.

They are not current truth unless corroborated by the current repository, immutable evidence, deterministic tests, and—when relevant—real-world outcomes.

## CI interpretation

Green CI proves only that the jobs and tests actually collected by that workflow passed on the identified commit. It does not prove that:

- test-looking files were collected;
- production entry points were exercised;
- external data was real or fresh;
- a model was calibrated;
- a recommendation was profitable;
- live operation was authorized.

The repository therefore includes a test-collection contract. Any `tests/test_*.py` module must contain a collectable pytest test or explicitly declare itself manual historical material.

## Betting-system release rule

No operational path may:

- manufacture a probability when model evidence is unavailable;
- substitute LLM confidence for calibrated probability;
- synthesize an executable price;
- force a non-zero stake after a zero or blocked Kelly result;
- increase sizing because of a winning streak;
- treat an operator click or generated skill as validation;
- emit a live recommendation while the canonical project status is research or paper-trading only.

`NO_BET` is a valid successful outcome.
