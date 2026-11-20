# Coding agent handoff — ONDM Monday prototype

## Objective

By 16 November 2026, deliver a polished **functional** Streamlit app demonstrating one small, image-capable VLM and three operator workflows. Do not train or benchmark models for this milestone.

## Source of truth

Use `data/semantic_pilot/graphs/*.json` for verified topology, `images/*.png` for the model image input, and `manifest.csv` for sample metadata. There are 30 paired samples. Keep graph source immutable during hypothetical failure analysis.

## Business scenarios

1. Service provisioning: input two existing ROADM IDs, calculate candidate shortest-distance route, highlight path and report kilometers/intermediate nodes. Never claim physical feasibility from NetworkX alone.
2. Link failure: select an existing edge, remove it on a temporary graph copy, show whether the network disconnects and available alternative paths.
3. Inventory-aware questions: build a local read-only inventory representation from graph JSON; expose a NetBox-compatible adapter interface but do not claim a real NetBox server is connected.

## Architecture

- Streamlit professional dark NOC-like UI: topology browser, graph/image view, chat, 3 example prompt buttons, evidence/tool trace, highlighted route/failure, synthetic-data status.
- One hardware-appropriate VLM with working image input and text generation; select only after checking hardware and actual model capabilities.
- Structured tool calling; NetworkX performs route and resilience math, VLM explains output. Validate tool inputs. Do not execute arbitrary model-generated Python on the host.
- Explicitly distinguish facts from graph JSON, VLM observations, deterministic computation and assumptions.
- Graceful handling of unknown node, no alternate path, unavailable model, and malformed input.
- Basic automated tests for graph loading, routing and failure scenarios.
- Optional read-only GNPy result display; interactive GNPy orchestration and full NetBox deployment are future milestones.

## Acceptance criteria

- Fresh clone runnable on Windows from documented installation steps.
- Genuine VLM response to a dataset topology image, not a hardcoded text sample.
- At least one tool selected/invoked by the agent with validated computed output.
- Three workflows operate on selected sample graphs with visible provenance.
- Correct handling of unreachable paths and unavailable model service.
- No secrets, real inventory, or large model checkpoints committed.

## Later ONDM work

Topology-group holdouts and leakage audit; systematic VLM metrics; full GNPy validation with equipment and transceiver thresholds; live read-only NetBox inventory; TopoBench compatibility review; optional model-generated code in a restricted sandbox.
