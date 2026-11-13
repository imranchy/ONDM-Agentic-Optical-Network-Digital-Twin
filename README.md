# ONDM Agentic Optical Network Digital Twin

Research prototype for a vision-language-model (VLM) copilot that interprets synthetic optical topologies and calls deterministic network engineering tools.

**Status — 13 November 2026:** This repository currently contains research documentation. The corrected dataset and research scripts are prepared for import; the Streamlit application, VLM agent, NetworkX tools and NetBox adapter are **not yet implemented**. GNPy converter scripts exist in the supplied research archive, but full end-to-end agent orchestration remains future work.

## Three business use cases

1. **Intelligent service provisioning:** choose ROADM endpoints, compute candidate routes and span distances, and explain route selection. Graph connectivity is not proof of optical feasibility.
2. **Fault impact and restoration:** simulate a span failure, inspect affected paths, and calculate alternatives without modifying the underlying dataset.
3. **Inventory-aware engineering:** answer site, device and link questions from a local synthetic inventory, with a future read-only NetBox connection.

## Intended architecture

- Streamlit: interactive topology viewer, engineering chat, workflow cards and tool traces.
- Small image-capable VLM: topology understanding, natural language intent, tool routing and explanations.
- NetworkX: tested graph computations and routing, separate from VLM-generated statements.
- GNPy: optical transmission feasibility based on documented equipment assumptions and configured thresholds.
- NetBox: future source of truth for site and equipment records, interfaces and connections.

## Dataset

Active pilot: **30 corrected synthetic optical network topologies**, each with graph JSON, a PNG topology rendering and annotation labels. ROADM nodes are switching sites. Inline amplification and transceiver attachments are modeled by the GNPy conversion work; they are not reliably rendered as individual symbols in these diagrams.

Existing train/validation/test assignments are preliminary, not verified leakage-free graph-family splits and not a benchmark. The previous 500 examples are **historical only**.

## Repository import

Use the provided `ONDM-GitHub-Starter.zip` to populate `data/semantic_pilot/`, `scripts/`, `integrations/gnpy/` and `simulations/examples/`, keeping paths intact. Binary data images are not yet present unless listed in the repository.

See [coding agent brief](docs/CODING_AGENT_BRIEF.md) for the Monday 16 November prototype scope and [GNPy status](docs/GNPY_INTEGRATION.md) for physical-layer limitations.

## Research and safety boundaries

All topologies are **synthetic**. Do not claim deployed-network validity, real operator inventory, live NetBox synchronization or GNPy optical feasibility without demonstrated tool execution. Never commit tokens, credentials, customer inventory or large model checkpoints.

License and publication rights are to be confirmed before reuse beyond the research project.
