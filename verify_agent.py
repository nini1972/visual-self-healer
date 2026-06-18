import os
import sys
import asyncio
import logging

if os.name == "nt":
    policy_cls = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if policy_cls is not None:
        asyncio.set_event_loop_policy(policy_cls())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify")

async def test_playwright_install():
    logger.info("Verifying Playwright installation and Chromium launch...")
    from playwright.async_api import async_playwright
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("about:blank")
            title = await page.title()
            logger.info(f"Successfully launched Chromium. Page title: '{title}'")
            await browser.close()
        return True
    except Exception as e:
        logger.error(f"Playwright verification failed: {str(e)}")
        return False

def test_imports():
    logger.info("Verifying imports...")
    try:
        import fastapi
        import uvicorn
        import google.genai
        import websockets
        logger.info("All library imports (fastapi, uvicorn, google.genai, websockets) are successful.")
        return True
    except ImportError as e:
        logger.error(f"Import failed: {str(e)}")
        return False

async def main():
    logger.info("=== Starting Verification of AuraHeal AI dependencies ===")
    
    # 1. Check imports
    imports_ok = test_imports()
    if not imports_ok:
        sys.exit(1)
        
    # 2. Check Playwright Chromium
    playwright_ok = await test_playwright_install()
    if not playwright_ok:
        sys.exit(1)
        
    logger.info("=== Verification Successful! Environment is ready. ===")

if __name__ == "__main__":
    asyncio.run(main())
