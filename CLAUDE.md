# Instructions for AI assistants working in this repo

1. **Read `STATUS.md` first**, then `docs/INTERFACES.md`, which is the contract between the server, the iPhone app and the Photon bridge. Reach into `poc/` only for the evidence behind a decision.
2. **Every change to logic gets unit tests, and you run them before calling it done:**
   - server: `cd server && ../poc/.venv/bin/python -m pytest -q tests` (or the venv you set up from `server/requirements.txt`). This includes the iOS and Photon contract tests.
   - Swift: `sh ios/check.sh` type-checks every file that builds on macOS and runs `ios/Tests/main.swift`. The ARKit/UIKit files only build in Xcode.
   - Photon scaffold: `cd photon-scaffold && npm test`. `photon/` (Utkarsh) and `frontend/` (the dashboard) are their owners' code, with their own tests: don't edit them unless asked.

   Report the pass count and whatever stays untested.
3. **Message formats change only in `docs/INTERFACES.md`,** together with the code and tests on both sides (`server/`, `ios/Marco/Core/Messages.swift`, `photon-scaffold/src/`). Regenerate `docs/INTERFACES.docx` with `poc/tools/md2docx.py`. Tell the other owners, including those of `photon/` and `frontend/`.
4. **Server security:**
   - bind 127.0.0.1 only (`marco/app.py` refuses anything else);
   - every route goes through `marco/auth.py`, which fails closed;
   - remote devices come in through `tailscale serve` with an allow-list;
   - never a public port, `tailscale funnel`, a made-up shared key, or a weakened gate.
5. **Keep the geometry rules:**
   - matrices are column-major;
   - images and depth stay in sensor orientation;
   - boxes become 3D with their own frame's pose and depth.
6. **Keep 1 frame/s:** the per-frame pipeline must stay well under 1 s. Re-run `server/tools/bench_frame.py` after changing detection.
7. **Repo hygiene:**
   - no secrets or tokens in files;
   - no references to other teams' projects;
   - recordings, downloaded datasets and other large or third-party data stay out (`.gitignore`);
   - do not push or post anywhere without the user's explicit go-ahead for that push.
8. **Context:** update `STATUS.md` (decisions, what landed, what's next) at the end of each piece of work, so a fresh session can pick up without the chat history.
