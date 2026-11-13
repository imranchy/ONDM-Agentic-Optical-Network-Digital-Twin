# Coding Agent Handoff — Monday 16 November 2026

**Goal:** Build a convincing Streamlit demonstration with ONE small local image-capable VLM. No fine-tuning, TopoBench scores, formal benchmarking or production deployment is required by Monday.

## Existing resources

Import the corrected 30-topology semantic pilot from the provided GitHub starter ZIP. Use its graph JSON as the authoritative graph structure and corresponding images as visual VLM inputs. Retain the available GNPy converter and sample outputs; no need to invoke GNPy live for the Monday demo.

## Required scenarios

1. **Service provisioning:** select real topology endpoints; invoke NetworkX shortest-path and alternative-path functions; show span distances and caveat optical feasibility.
2. **Fault impact:** select an existing edge; simulate removal on a graph copy; recalculate connectivity and possible restoration paths.
3. **Inventory lookup:** query synthetic sites, ROADMs and links derived from the same topology, with a future read-only NetBox adapter boundary. Do not imply a live NetBox service exists.

## Architecture and acceptance criteria

- Polished dark Streamlit UI, topology selector, graph viewer, original image, question input, suggested prompts, highlighted routes and tool traces.
- Actual multimodal inference with a small locally runnable VLM; provide pluggable adapter, model configuration and honest error handling when model unavailable.
- Deterministic, typed NetworkX tools for shortest paths, path diversity, failures, inventories.
- Model may **propose** tool invocations, but arbitrary generated Python must **not** be executed on host. Add an isolated experimental sandbox later if needed.
- Validate schema and node IDs, surface evidence sources and tool outputs, avoid hardcoded answers.
- Smoke-test all three workflows against existing graphs; document Windows installation and launcher.
- Secrets in environment variables only; synthetic-data labeling in UI.

## Later research phases

Expanded equipment fidelity, full GNPy quality-of-transmission simulations, read-only real NetBox integration, topology-to-inventory extraction, leakage-free grouped splits and independent VLM benchmarks.
