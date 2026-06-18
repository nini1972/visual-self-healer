import os
import asyncio
import warnings

import uvicorn

if os.name == "nt":
    policy_cls = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if policy_cls is not None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            # Uvicorn's asyncio setup may force WindowsSelectorEventLoopPolicy.
            # Remap it so Playwright subprocess APIs keep working on Python 3.14.
            asyncio.WindowsSelectorEventLoopPolicy = policy_cls
            asyncio.set_event_loop_policy(policy_cls())


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
