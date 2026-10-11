# 04 — Install copies the starter on request and honours `CLAUDE_CONFIG_DIR`

Status: resolved
Mode: AFK
Blocked by: None — can start immediately
Spec: [PRD](../PRD.md), "The Workflow library and install" and "The starter and the personal Workflow"; ADRs 0049, 0052

**What to build:** Four changes to install and the shipped Workflows.

1. **The starter ships in the package.** It is the draft on branch `prototype/starter-workflow`, moved into the package, declared as package data, and read as a package resource.
2. **`naiad install --starter [--force]`** copies it into the library as a regular file:
   - no file there: the starter is written;
   - a byte-identical file: it is rewritten;
   - a differing file or a symlink of that name: refused with "starter.toml differs from the shipped starter; pass --force or move it aside";
   - `--force`: overwrites.

   A bare `naiad install` touches the library not at all. Linking shipped Workflows is removed entirely: the checkout-relative shipped directory, the link function, the copy refusal and its wording, and the "no workflows directory" branch.
3. **Install targets follow `CLAUDE_CONFIG_DIR`.** Hooks go to `$CLAUDE_CONFIG_DIR/settings.json` and the adopt skill to `$CLAUDE_CONFIG_DIR/skills` when the variable is set, and to `~/.claude` otherwise. One function computes the directory, and ticket 09's doctor reuses it. `--settings` and `--skills` keep working.
4. **The personal Workflow's `pull-request` Prompt reads `.matt-pocock.toml`** in both places it named `naiad.toml`. The shipped-workflow invariant tests run parametrised over the packaged starter and `workflows/matt-pocock.toml`.

A dangling hand-made link in the library is named as broken by the resolver rather than reported as a missing name.

- [ ] `naiad install --starter` into an empty library writes a regular `starter.toml`, and `naiad queue add starter "…"` resolves it.
- [ ] The re-run cases behave as listed: identical rewritten, differing refused, symlink refused, `--force` overwrites.
- [ ] Bare `naiad install` leaves the library byte-for-byte unchanged.
- [ ] With `CLAUDE_CONFIG_DIR` set, the hooks and the skill land under it; unset, under `~/.claude`.
- [ ] The invariant tests pass for both Workflow files.
- [ ] A broken link in the library is reported as broken by name resolution.
- [ ] Built test-first, Refactor verdict recorded.

## Refactor verdict

Candidates considered: the empty-variable rule duplicated from `naiad_home` (keep: two lines, and `naiad_home` is a different domain); `default_settings_path` and `default_skills_root` as thin wrappers (keep: they mirror `default_runs_root`); `write_atomically` taking bytes (keep: the byte-identical copy needs it, and it is one branch); the parametrised invariant helpers `each_state` and `each_workflow` (done: derived from the loaded files, so no list is written out); `--force` refused without `--starter` (keep: a silent no-op would read as a forced install). Committed as dcfc3c0.
