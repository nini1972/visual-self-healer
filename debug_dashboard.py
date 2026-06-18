import os
import asyncio
from playwright.async_api import async_playwright

if os.name == "nt":
    policy_cls = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if policy_cls is not None:
        asyncio.set_event_loop_policy(policy_cls())

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Monitor network requests
        page.on("request", lambda req: print(f"REQUEST: {req.method} {req.url}"))
        
        # Monitor console logs
        page.on("console", lambda msg: print(f"BROWSER CONSOLE: [{msg.type.upper()}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err.message}\n{err.stack}"))
        
        print("Navigating to http://127.0.0.1:8500/sandbox/index.html... ")
        try:
            await page.goto("http://127.0.0.1:8500/sandbox/index.html", wait_until="load", timeout=15000)
            await asyncio.sleep(3.0)
            await page.screenshot(path="sandbox_test.png")
            print("Successfully captured screenshot sandbox_test.png!")
        except Exception as e:
            print(f"Error navigating: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
