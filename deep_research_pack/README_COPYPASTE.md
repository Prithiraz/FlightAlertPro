# Deep Research Copy/Paste Guide

## What to paste into ChatGPT Deep Research

Follow these 5 steps for the best results:

1. **Start with the Project Summary.**
   Copy the entire contents of `00_PROJECT_SUMMARY.md` as your opening message. It gives Deep Research the full context: what the app does, the tech stack, current status (working vs broken), run commands, and Codespaces URLs.

2. **Paste the Known Errors file next.**
   Copy the entire contents of `05_KNOWN_ERRORS.md` immediately after. This is the most actionable file — it lists each bug, its root cause (with file + line number), and the likely fix. Ask Deep Research to prioritize these.

3. **Paste specific supporting files as needed.**
   - If you want help fixing the API shape mismatch → paste `04_API_ENDPOINTS.md`.
   - If you want help setting up environment variables → paste `02_CONFIG_AND_ENV.md`.
   - If you want help with auth redirect URLs → paste `03_AUTH_FLOW.md`.
   - If you need to explain the file structure → paste `01_REPO_MAP.md`.

4. **Frame your prompt clearly.**
   After pasting, write a focused question, for example:
   > *"Given the project summary and known errors above, give me the exact code changes needed to fix Errors 1–3 (search schema mismatch, SUPABASE_KEY typo, and Stripe checkout arg mismatch). Show diffs."*

5. **Do not paste raw code files or secrets.**
   The pack files contain no secret values (all are `REDACTED`). Do not copy any actual `.env` file contents or real API keys into the chat. The pack is designed to be safe to paste as-is.
