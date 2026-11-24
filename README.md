# YouTube Video Intelligence MCP Server

An MCP server that lets an AI client discover, analyse and curate YouTube videos for an authorised user, using only the official YouTube Data API v3. Built by Team Larpers.

## Status

Stage 0: repository bootstrap. See CHANGELOG.md.

## Quick start

    python -m venv .venv
    source .venv/bin/activate      # Windows: .venv\Scriptsctivate
    make setup
    make lint test

## Branching

Trunk-based. main is protected. Branches are short-lived: feat/Bxx-name, fix/issue-N, docs/..., brain/..., test/..., chore/.... Pull requests are squash-merged after one human review.

## Rules for contributors and AI agents

See AGENTS.md.
