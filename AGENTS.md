# Project Coding Guidelines

This project follows the caution-first coding style from multica-ai/andrej-karpathy-skills, adapted for this repository.

## Assumptions

- The final demo should run locally without cloud LLM calls.
- AIHub datasets and API keys must not be committed.
- Ollama is optional at development time, but the code must call it when a local server is available.

## Simplicity

- Keep the prototype small enough to inspect in one sitting.
- Prefer standard-library code unless a dependency is necessary for the requested demo.
- Add optional integrations only behind clear commands or environment variables.

## Surgical Changes

- Touch only files needed for the RAG prototype, evaluation loop, and repository setup.
- Do not commit generated private data, raw AIHub files, or secrets.

## Verifiable Goals

1. Build an index from sample QA -> verify with a CLI command.
2. Ask a question against the local index -> verify answer and evidence IDs.
3. Run retrieval evaluation -> verify CSV output.
4. Publish the repository only after local checks pass.

Reference: https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md
