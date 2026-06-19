# AuraHeal AI Deployment Notes

## Runtime

- Python: 3.14
- Backend: FastAPI + Uvicorn
- Browser audit: Playwright Chromium
- AI model: Gemini via `google-genai`

## Start the backend

```powershell
.\.venv\Scripts\python.exe backend\run_server.py
```

The backend listens on:

```text
http://127.0.0.1:8500
```

## Install Playwright browsers

If Chromium is not installed, run:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Visual audit verification

The fixed audit path uses:

```text
http://127.0.0.1:8500/sandbox/index.html
```

A successful audit captures:

- Viewport: `1280x800`
- Screenshot path: `backend/sandbox/screenshots/iteration_{n}.jpeg`
- Expected result: non-empty base64 screenshot returned to the websocket client

## Known fix

`backend/agent.py` now imports `asyncio`, which was required by:

```python
await asyncio.sleep(2.5)
```

Without this import, Playwright launched and loaded the page, but screenshot capture failed with:

```text
CAPTURE_FAILED: name 'asyncio' is not defined
```

That caused the frontend error:

```text
Browser audit failure: No valid screenshot captured.
```

## Production notes

- The sandbox uses `cdn.tailwindcss.com`; this is acceptable for local iteration but should be replaced with a compiled Tailwind build for production.
- Restart the backend after changing `backend/agent.py` because Uvicorn is running with `reload=False`.
- The browser audit does not require a Gemini API key; the key is only required for code generation and visual critique steps.
