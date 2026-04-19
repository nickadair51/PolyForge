# PolyForge

Multi-LLM Code Review & Execution Platform

PolyForge is a CLI tool that fans out code questions to Claude, GPT-4o, and Gemini in parallel. Each LLM's suggested changes are applied to an isolated repo snapshot, executed in a Docker container, and compared via a blind synthesis evaluation that recommends the best solution.

## Quick Start

```bash
pip install -e .
polyforge --repo /path/to/project
```

## How It Works

1. Point PolyForge at your repo
2. Ask a question about your code
3. Select up to 5 relevant files (by filename or path)
4. Confirm the estimated cost
5. PolyForge queries all selected LLMs in parallel
6. Each response is applied to an isolated repo copy
7. Docker containers run your tests against each modified copy
8. A blind synthesis evaluation recommends the best solution

## CLI Usage

```bash
polyforge --repo <path>                          # all 3 models (default)
polyforge --repo <path> --models claude,gpt4o    # specific models
polyforge --repo <path> --verbose                # show Docker stdout/stderr
polyforge --repo <path> -v                       # short form
```

## Requirements

- Python 3.11+
- Docker Desktop (macOS) or Docker Engine (Linux)
- At least one API key set as an environment variable:
  - `ANTHROPIC_API_KEY` (Claude)
  - `OPENAI_API_KEY` (GPT-4o)
  - `GOOGLE_API_KEY` (Gemini)

## Supported Project Types

| Type | Detected By | Docker Image | Test Command |
|------|------------|--------------|-------------|
| Node.js | package.json | node:20-alpine | npm ci && npm test |
| Python | requirements.txt / pyproject.toml | python:3.11-slim | pip install + pytest |
| Maven | pom.xml | maven:3.9-openjdk-17 | mvn test -B |
| Gradle | build.gradle | gradle:8-jdk17 | gradle test --no-daemon |
| Rust | Cargo.toml | rust:1.75-slim | cargo test |

## Git Branching

```
main              # production-ready code only
develop           # integration branch
feature/<name>    # one branch per component
fix/<name>        # bug fixes
chore/<name>      # non-code work (docs, config, dependencies)
```

## Docs

- `docs/PolyForge_Requirements_v1.md` — product requirements
- `docs/PolyForge_Architecture_v1.md` — system architecture
- `CLAUDE.md` — Claude Code context and project conventions
