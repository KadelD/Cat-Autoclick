---
name: release-prep
description: >-
  Audits, optimizes, and builds Cat Autoclick for a Windows release.
  Use when preparing a release, shipping v1, building the exe, release checklist,
  audit before ship, or the user asks to release-prep / prep release.
---

# Cat Autoclick — Release Prep

Workflow for first and later Windows releases. Follow phases in order. Do not skip the audit gate.

## When to run

- User asks to prepare / ship / release / build dist
- Major feature freeze before tagging
- After packaging or settings changes that affect the exe

## Phase 1 — Audit

Copy and track:

```
Release audit:
- [ ] Imports: python -c "from app.ui.main_window import run_app"
- [ ] Settings load/save + hotkey normalize OK
- [ ] Recorder swallow matches settings hotkeys
- [ ] OCR gate: ocr_enabled=False never constructs EasyOCR
- [ ] Stop releases held keys/buttons
- [ ] project_root() works frozen + source
- [ ] Spec datas: presets, assets, templates
- [ ] .gitignore: dist/, build/, .venv/, settings.json (user-local)
- [ ] README/AGENTS match current behavior
- [ ] No secrets / credentials in tree
- [ ] Demo presets load; templates/.gitkeep present
```

Severity:

| Level | Meaning | Action |
|-------|---------|--------|
| Critical | Crash, data loss, broken stop/hotkeys, frozen path wrong | Must fix before build |
| Major | Wrong defaults, OCR leak when disabled, docs lie | Fix before release |
| Minor | Polish, unused code, tip copy | Optional same pass |

Read first: `AGENTS.md`, `cat-autoclick.spec`, `build_exe.bat`, `app/core/store.py`, `app/core/settings.py`, `app/ui/main_window.py`.

## Phase 2 — Optimize (safe only)

Allowed without asking:

- Dead imports / obvious bugs found in audit
- Ensure `settings.json` is gitignored (user machine state)
- Exclude `__pycache__`, test junk from ship notes
- Spec: keep EasyOCR lazy at runtime; do not force full `collect_all(easyocr)` unless audit proves missing modules at runtime
- Tiny UX/docs fixes that unblock release

Do **not** in this pass:

- Large refactors, new features, tray, per-preset hotkeys
- Commit / tag / push unless user explicitly asks
- Force-include entire EasyOCR model tree into the exe (prefer `run.bat` for OCR)

## Phase 3 — Build

```bat
build_exe.bat
```

Expect: `dist/CatAutoclick/CatAutoclick.exe`

Smoke (manual or scripted):

1. Launch exe → window appears
2. Settings → Save → `settings.json` next to exe
3. Record briefly → HUD; stop releases input
4. Play demo preset once
5. If OCR on: first OCR may download models (network) — note in release notes

If build fails: fix Critical, rebuild. Do not ship a failed dist.

## Phase 4 — Release notes draft

Return to the user (do not invent git tags):

```markdown
## Cat Autoclick vX.Y.Z (draft)

### Ship
- Artifact: `dist/CatAutoclick/` (folder — copy whole directory)
- Prefer `run.bat` for heavy OCR; exe is best-effort for vision

### Highlights
- …

### Known limits
- EasyOCR first-run download / large size
- Some elevated apps block injected input

### Verify
- [ ] … checklist results
```

## Project commands

```bat
run.bat
build_exe.bat
```

```bash
.venv/Scripts/python -c "from app.ui.main_window import run_app; print('import ok')"
```

## Conventions (do not break)

- UI English-only; update `AGENTS.md` + `README.md` when behavior changes
- Playback/record on background threads; UI via `after(0, …)`
- Coordinates monitor-local via `monitors.py`
- No commit unless user asks
