# Coding-agent instruction files

Babel keeps its instructions for coding agents (Claude Code, Codex, Cursor, Copilot and others) in
`AGENTS.md` files: one at the repository root, and one in each directory whose code has conventions
of its own. Root `AGENTS.md` lists those directories under "Directory-scoped instructions". This
page covers how the files are arranged, how to add one, and how to check that Claude Code loads
them.

## Why `AGENTS.md`, and never `CLAUDE.md`

Codex, Cursor and Copilot read `AGENTS.md` natively. Claude Code reads a directory's `AGENTS.md`
only when that directory has no `CLAUDE.md`, so a `CLAUDE.md` added anywhere silently hides the
`AGENTS.md` beside it from Claude Code (#1238). One file name therefore serves every agent, and
`tests/test_agent_files.py` fails if any `CLAUDE.md` or `CLAUDE.local.md` is tracked, in any
directory (`.claude/` included) or letter case.

If `/init` or anything else creates a `CLAUDE.md`, merge what it says into the `AGENTS.md` beside it
(creating one if needed) and delete it. Don't fall back on a one-line `@AGENTS.md` `CLAUDE.md` shim:
the test rejects that too, and the Claude Code versions below don't need one.

## Adding a directory-scoped `AGENTS.md`

1. Name it exactly `AGENTS.md`. The test fails on any other letter case, since an agent on a
   case-sensitive file system won't find an `agents.md`.
2. Add a list item for its directory under "Directory-scoped instructions" in root `AGENTS.md`. The
   test compares that list with the tracked files in both directions, and reads only the backticked
   paths *before* each item's em-dash (`` - `src/foo/` — what it covers ``), so a directory
   mentioned in a description doesn't count as listed.
3. A file covers its directory and everything below it: Claude Code loads `src/tools/AGENTS.md` for
   a file in `src/tools/memory/`, which has no file of its own.

## Which Claude Code versions read these files

Claude Code needs version 2.1.290 or later, and it doesn't warn you when it can't read them. Claude
Code's changelog dates `AGENTS.md` support to 2.1.277, extends it to Amazon Bedrock, Google Vertex
AI, Microsoft Foundry, LLM gateways and telemetry-disabled sessions in 2.1.281, and fixes a
subdirectory's `AGENTS.md` not being attached for an @-mentioned file in 2.1.290.

A version before 2.1.277, a session whose "Project instructions" setting in `/config` no longer
reads `AGENTS.md`, or one with a `Read` deny rule that covers `AGENTS.md` (say
`--disallowedTools 'Read(**/AGENTS.md)'`) loads none of this guidance. Upgrade Claude Code, or fix
that setting, rather than adding a `CLAUDE.md`.

## Checking what Claude Code loads

Run `claude -p` asking it to read one file in each of a few directories, then look in its session
transcript (`~/.claude/projects/<dir>/<session>.jsonl`). Root `AGENTS.md` is in the startup
`instructions` attachment, and each nested one arrives as a `hook_additional_context` attachment
right after the first Read in its directory or below it.

Don't deny Read on `AGENTS.md` to stop the model opening the files itself: that also stops them
loading. The transcript's own Read calls show whether it opened one.

Last checked with Claude Code 2.1.327, which loaded root `AGENTS.md` at startup, and
`tests/AGENTS.md`, `input_data/manual_concords/AGENTS.md` and `src/tools/AGENTS.md` after a Read in
`tests/`, `input_data/manual_concords/` and `src/tools/memory/`.
