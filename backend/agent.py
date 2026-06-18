import sys
import asyncio
import os
import json
import logging
import base64
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Force Windows to use the ProactorEventLoop so Playwright can spawn Chromium
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logger = logging.getLogger("auraheal")

# ==========================================
# PYDANTIC SCHEMAS FOR STRUCTURED OUTPUTS
# ==========================================

class InitialCodeResponse(BaseModel):
    title: str = Field(
        description="The clean text title of the web application page."
    )
    css: str = Field(
        description="Highly essential custom CSS stylesheet rules (without <style> tags). Rely 90% on Tailwind utility classes; only write custom CSS here for special animations, custom keyframes, or glassmorphic gradients."
    )
    html_body: str = Field(
        description="The HTML layout structure inside the body (without <body> or <script> tags). Make it structurally complete with unique element IDs, utilizing Tailwind CSS utility classes heavily."
    )
    js_script: str = Field(
        description="Complete functional JavaScript logic (without <script> tags). Make elements fully active and responsive to user interaction."
    )

class ReplacementChunk(BaseModel):
    selector: str = Field(
        description="The CSS selector targeting the specific component/element to replace (e.g., '#hero-section', '#submit-btn'). DO NOT target broad wrappers like 'body', 'html', or 'style' tags unless absolutely required."
    )
    replacement_content: str = Field(
        description="The complete new inner HTML markup or code for the specified selector. If targeting a script or style tag, provide raw code; otherwise, provide pure HTML inner contents."
    )

class CritiqueResponse(BaseModel):
    is_perfect: bool = Field(
        description="Set to True ONLY if the web page looks professional, stunning, has flawless visual symmetry, matches the prompt, and contains zero console errors. Set to False if adjustments are needed."
    )
    feedback: str = Field(
        description="Constructive and professional critique regarding layout balance, colors, typography alignment, and broken components."
    )
    replacements: list[ReplacementChunk] = Field(
        default=[],
        description="A list of hyper-targeted DOM modifications. Leave this array completely empty if is_perfect is True."
    )

# ==========================================
# AGENT ARCHITECTURE
# ==========================================

class VisualSelfHealerAgent:
    def __init__(self, api_key: str, sandbox_dir: str, server_url: str):
        self.api_key = api_key
        self.sandbox_dir = sandbox_dir
        self.server_url = server_url
        self.code_path = os.path.join(self.sandbox_dir, "index.html")
        self.screenshots_dir = os.path.join(self.sandbox_dir, "screenshots")
        
        os.makedirs(self.sandbox_dir, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # Initialize Google GenAI Client
        self.client = genai.Client(api_key=api_key)

    async def generate_initial_code(self, prompt: str, send_log_fn) -> str:
        await send_log_fn("INFO", f"Generating initial optimized code for: '{prompt}'...")
        
        system_prompt = (
            "You are a elite frontend software engineer and visual UI designer specializing in high-end, cohesive digital experiences.\n"
            "Design Rules:\n"
            "1. TAILWIND FIRST: Rely entirely on standard preloaded Tailwind CSS classes inside your HTML structure. Avoid massive blocks of custom CSS.\n"
            "2. ANIMATIONS & REFINEMENT: Only use the custom CSS block for advanced CSS layout animations, premium glassmorphism filters, or custom variable setups.\n"
            "3. DEFENSIVE JAVASCRIPT: Every single document.querySelector or getElementById MUST be instantly checked for null before manipulating its classList, styles, or addEventListener. Example: const target = document.querySelector('#id'); if (target) { target.addEventListener(...); }\n"
            "4. ZERO PLACEHOLDERS: Generate real text contents, real numbers, and high-fidelity mock datasets."
        )

        user_content = f"Create a fully functional, breathtaking, and beautifully stylized component for: '{prompt}'."

        try:
            # Using Structured Outputs via response_schema
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=InitialCodeResponse,
                    temperature=0.4, # Balanced creativity
                )
            )
            
            parsed = json.loads(response.text or "{}")
            title = parsed.get("title") or "AuraHeal Dashboard"
            css = parsed.get("css", "").strip()
            html_body = parsed.get("html_body", "").strip()
            js_script = parsed.get("js_script", "").strip()

            # Compile into unified template
            code = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Inter:wght@300;400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        {css}
    </style>
</head>
<body class="bg-slate-940 text-slate-100 min-h-screen">
    {html_body}
    <script>
        // Self-contained logic loop
        (function() {{
            {js_script}
        }})();
    </script>
</body>
</html>"""
            
            with open(self.code_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            await send_log_fn("INFO", "Initial clean code baseline compiled into sandbox.")
            return code
            
        except Exception as e:
            await send_log_fn("ERROR", f"Failed to generate initial code: {str(e)}")
            raise e

    async def audit_sandbox(self, iteration: int, send_log_fn) -> tuple[str, list[str]]:
        await send_log_fn("INFO", f"Launching lightweight visual audit (Iteration {iteration})...")
        
        sandbox_url = f"{self.server_url}/sandbox/index.html"
        # Store screenshots as lightweight JPEGs
        screenshot_path = os.path.join(self.screenshots_dir, f"iteration_{iteration}.jpeg")
        
        console_messages = []
        page_errors = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Default presentation boundary viewport
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            page.on("console", lambda msg: console_messages.append(f"[{getattr(msg, 'type', 'LOG').upper()}] {getattr(msg, 'text', '')}"))
            
            def safe_page_error(err):
                msg = getattr(err, 'message', str(err))
                stack = getattr(err, 'stack', '')
                page_errors.append(f"EXCEPTION: {msg}\n{stack}")

            page.on("pageerror", safe_page_error)
        
                      
            try:
                await send_log_fn("INFO", f"Auditing view layout at {sandbox_url}...")
                await page.goto(sandbox_url, timeout=12000, wait_until="load")
                await asyncio.sleep(2.5) # Allow CDN rendering overheads
                
                # Element interaction test
                buttons = await page.query_selector_all("button")
                if buttons:
                    try:
                        await buttons[0].click(timeout=800)
                        await asyncio.sleep(0.4)
                    except Exception:
                        pass
                
                # OPTIMIZATION 1: Output lightweight JPEG, do not capture unbounded full_page blocks
                await page.screenshot(path=screenshot_path, type="jpeg", quality=60, full_page=False)
                await send_log_fn("INFO", f"Compressed snapshot saved.")
                
            except Exception as e:
                page_errors.append(f"CAPTURE_FAILED: {str(e)}")
            finally:
                await browser.close()
                
        # Base64 compression readback
        screenshot_b64 = ""
        if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
            with open(screenshot_path, "rb") as img:
                screenshot_b64 = base64.b64encode(img.read()).decode("utf-8")
                
        # OPTIMIZATION 2: Strictly cap rogue console loops (prevent token injection scaling)
        MAX_LOG_THRESHOLD = 15
        truncated_console = console_messages[:MAX_LOG_THRESHOLD]
        if len(console_messages) > MAX_LOG_THRESHOLD:
            truncated_console.append(f"... omitted {len(console_messages) - MAX_LOG_THRESHOLD} repetitive log lines.")
            
        all_logs = page_errors + truncated_console
        return screenshot_b64, all_logs

    async def run_healer_step(self, prompt: str, code: str, screenshot_b64: str, logs: list[str], iteration: int, send_log_fn) -> tuple[bool, str, str]:
        if not screenshot_b64:
            raise ValueError("Browser audit failure: No valid screenshot captured.")

        await send_log_fn("INFO", f"Analyzing viewport tokens through structured visual intelligence...")
        logs_str = "\n".join(logs) if logs else "No anomalies or console errors found."
        
        contents = [
            types.Part.from_bytes(
                data=base64.b64decode(screenshot_b64),
                mime_type="image/jpeg" # Matched to audit format
            ),
            f"Original Target Directive: {prompt}\n\n"
            f"Current Active HTML Source:\n```html\n{code}\n```\n\n"
            f"Current Active Browser Output logs:\n{logs_str}\n\n"
            "Execution Orders:\n"
            "1. Review layout alignment, spacing breaks, contrast scales, and typography bugs on the image snapshot.\n"
            "2. Read console errors. Fix any exceptions or script execution boundaries.\n"
            "3. If adjustments are necessary, provide atomic targeted selector changes. CRITICAL: Do not overwrite large parent layout blocks, structural tags, or rewrite global style blocks completely unless a change is directly needed inside them."
        ]
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CritiqueResponse, # Guarantees reliable JSON object shape
                    temperature=0.1, # Enforces clinical editing precision
                )
            )
            
            result_json = json.loads(response.text or "{}")
            is_perfect = result_json.get("is_perfect", False)
            feedback = result_json.get("feedback", "")
            reps_data = result_json.get("replacements", [])
            
            replacements = [
                ReplacementChunk(
                    selector=r.get("selector", ""),
                    replacement_content=r.get("replacement_content", "")
                )
                for r in reps_data
            ]
            
            healed_code = code
            if not is_perfect and replacements:
                healed_code = self.apply_replacements(code, replacements)
                
                if not self._is_valid_html(healed_code):
                    await send_log_fn("WARNING", "Healed syntax validation check failed. Rollback triggered.")
                    return False, feedback + " [Heal rejected: invalid syntax structural mutation]", code
                    
                with open(self.code_path, "w", encoding="utf-8") as f:
                    f.write(healed_code)
                await send_log_fn("INFO", f"Applied {len(replacements)} precise components corrections.")
            
            return is_perfect, feedback, healed_code
            
        except Exception as e:
            await send_log_fn("ERROR", f"Healer iteration routine exception: {str(e)}")
            raise e

    def apply_replacements(self, code: str, replacements: list[ReplacementChunk]) -> str:
        soup = BeautifulSoup(code, "html.parser")
        for rep in replacements:
            selector = rep.selector.strip()
            content = rep.replacement_content or ""
            if not selector or not content.strip():
                continue
            
            element = soup.select_one(selector)
            if element:
                # Handle special embedded text code zones safely
                if selector in ("style", "script") or element.name in ("style", "script"):
                    element.string = content
                else:
                    element.clear()
                    new_nodes = BeautifulSoup(content, "html.parser")
                    element.append(new_nodes)
            else:
                logger.warning(f"Target selector block '{selector}' was dropped by model alignment error.")
        return str(soup)

    def _is_valid_html(self, code: str) -> bool:
        if not code or len(code.strip()) < 200 or "<body" not in code.lower():
            return False
        soup = BeautifulSoup(code, "html.parser")
        body = soup.find("body")
        return body is not None and len(body.decode_contents().strip()) > 100