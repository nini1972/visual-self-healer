import sys
import asyncio

# Force Windows to use the ProactorEventLoop so Playwright can spawn Chromium
# This MUST be done before importing uvicorn, as uvicorn may create a loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import uvicorn

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(base_dir, "..", "frontend")

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8500,
        # On Windows + Python 3.14, reload mode forces SelectorEventLoop and breaks
        # Playwright subprocess creation (NotImplementedError in create_subprocess_exec).
        reload=False,
    )
