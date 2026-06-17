import os
import asyncio
import json
import logging
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright
import base64
from bs4 import BeautifulSoup

logger = logging.getLogger("auraheal")

class ReplacementChunk(BaseModel):
    selector: str = Field(
        description="The CSS selector of the tag/element to replace (e.g., 'style', 'script', or specific element IDs like '#dashboard', '#buttons-panel')."
    )
    replacement_content: str = Field(
        description="The complete new HTML/CSS/JS inner content for the specified selector. For 'style' and 'script' tags, provide the raw CSS/JS code directly. For HTML elements, provide the HTML structure."
    )

class CritiqueResponse(BaseModel):
    is_perfect: bool = Field(
        description="Set to True if the web page matches the prompt, is visually stunning, has zero layout issues, and has no console errors. Set to False if improvements are needed."
    )
    feedback: str = Field(
        description="Detailed review of visual design, contrast, alignment, typography, errors, and what needs to be fixed."
    )
    replacements: list[ReplacementChunk] = Field(
        default=[],
        description="List of specific DOM element/tag inner HTML replacements to apply. Leave empty if is_perfect is True."
    )

class VisualSelfHealerAgent:
    def __init__(self, api_key: str, sandbox_dir: str, server_url: str):
        """
        api_key: Gemini API key
        sandbox_dir: Directory where backend/sandbox/index.html is stored
        server_url: Base URL (e.g., http://localhost:8500) where static files are served
        """
        self.api_key = api_key
        self.sandbox_dir = sandbox_dir
        self.server_url = server_url
        self.code_path = os.path.join(self.sandbox_dir, "index.html")
        self.screenshots_dir = os.path.join(self.sandbox_dir, "screenshots")
        
        os.makedirs(self.sandbox_dir, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # Initialize Gemini Client
        # The new Google GenAI SDK (google-genai) looks for GEMINI_API_KEY in the constructor or env
        self.client = genai.Client(api_key=api_key)

    async def generate_initial_code(self, prompt: str, send_log_fn) -> str:
        await send_log_fn("INFO", f"Generating initial code for prompt: '{prompt}'...")
        
        system_prompt = (
            "You are a master frontend engineer and visual UI/UX designer. "
            "You design beautiful, modern, responsive, and highly premium web application components.\n"
            "You must structure your response using exact delimiters for each section as follows:\n"
            "<!-- TITLE -->\n"
            "[Provide the page title here]\n"
            "<!-- CSS -->\n"
            "[Provide custom CSS stylesheet rules here (without <style> tags). Use variables, keyframes, shadows, and glassmorphic designs.]\n"
            "<!-- HTML_BODY -->\n"
            "[Provide HTML markup code for the body container here (without <body> or <script> tags). Make it structurally complete with unique element IDs.]\n"
            "<!-- JS_SCRIPT -->\n"
            "[Provide complete JavaScript logic here (without <script> tags). Make buttons active, dynamic, and interactive.]\n\n"
            "Follow these design rules:\n"
            "1. Design Aesthetics: Use vibrant color palettes, dark modes, Outfit/Inter typography, and drop shadows.\n"
            "2. Interactive Design: Include hover effects, active button transitions, and keyframe animations.\n"
            "3. Tailwind CSS classes are supported and preloaded in the template, so feel free to use standard Tailwind classes in your HTML body.\n"
            "4. Zero placeholders: Do not use placeholders. All copy and functional features must be written out."
        )

        user_content = f"Create a fully interactive, visually stunning, and highly premium web application for: '{prompt}'."

        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                    max_output_tokens=8192,
                )
            )
            
            text = response.text
            
            # Parse text with HTML comment delimiters
            markers = {
                "title": "<!-- TITLE -->",
                "css": "<!-- CSS -->",
                "html_body": "<!-- HTML_BODY -->",
                "js_script": "<!-- JS_SCRIPT -->"
            }
            
            indices = {}
            for key, marker in markers.items():
                idx = text.find(marker)
                if idx != -1:
                    indices[key] = idx + len(marker)
                    
            sorted_keys = sorted(indices.keys(), key=lambda k: indices[k])
            
            parsed = {"title": "AuraHeal Dashboard", "css": "", "html_body": "", "js_script": ""}
            for i, key in enumerate(sorted_keys):
                start = indices[key]
                if i + 1 < len(sorted_keys):
                    next_key = sorted_keys[i + 1]
                    end = text.find(markers[next_key])
                    parsed[key] = text[start:end].strip()
                else:
                    parsed[key] = text[start:].strip()
            
            # Clean up potential markdown formatting that the model might wrap sections in
            for key in ["css", "html_body", "js_script"]:
                val = parsed[key]
                if val.startswith("```"):
                    nl = val.find("\n")
                    if nl != -1:
                        val = val[nl+1:]
                if val.endswith("```"):
                    val = val[:-3]
                parsed[key] = val.strip()

            title = parsed["title"] or "AuraHeal Dashboard"
            css = parsed["css"]
            html_body = parsed["html_body"]
            js_script = parsed["js_script"]
            
            # Compile structured code into standard single-file HTML
            code = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Inter:wght@300;400;500;700&display=swap" rel="stylesheet">
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        {css}
    </style>
</head>
<body>
    {html_body}
    <script>
        {js_script}
    </script>
</body>
</html>"""
            
            # Write to sandbox file
            with open(self.code_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            await send_log_fn("INFO", "Initial code successfully written to sandbox.")
            return code
            
        except Exception as e:
            await send_log_fn("ERROR", f"Failed to generate initial code: {str(e)}")
            raise e

    async def audit_sandbox(self, iteration: int, send_log_fn) -> tuple[str, list[str]]:
        """
        Runs Playwright to open the sandbox, captures a screenshot, and fetches console logs.
        Returns (screenshot_base64, list_of_errors)
        """
        await send_log_fn("INFO", f"Launching headless browser to audit sandbox (Iteration {iteration})...")
        
        # We point to the local HTTP server hosting the sandbox
        sandbox_url = f"{self.server_url}/sandbox/index.html"
        screenshot_path = os.path.join(self.screenshots_dir, f"iteration_{iteration}.png")
        
        console_messages = []
        page_errors = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            # Attach listeners
            page.on("console", lambda msg: console_messages.append(f"[{msg.type.upper()}] {msg.text}"))
            page.on("pageerror", lambda err: page_errors.append(f"EXCEPTION: {err.message}\n{err.stack}"))
            
            try:
                await send_log_fn("INFO", f"Navigating to {sandbox_url}...")
                # Wait for 'load' instead of 'networkidle' to prevent CDN/font loading timeouts
                await page.goto(sandbox_url, timeout=15000, wait_until="load")
                # Wait 3 seconds for Tailwind CDN, Google Fonts, and animations to fully render
                await asyncio.sleep(3.0)
                
                # Perform basic interactions if any exist, e.g. checking buttons don't throw errors
                await send_log_fn("INFO", "Testing interactive page elements...")
                buttons = await page.query_selector_all("button")
                if buttons:
                    await send_log_fn("INFO", f"Found {len(buttons)} button(s). Clicking the first one to test interactive logs...")
                    try:
                        # Click the first button to check for basic runtime exception
                        await buttons[0].click(timeout=1000)
                        await asyncio.sleep(0.5)
                    except Exception as click_err:
                        console_messages.append(f"[WARNING] Click test skipped/failed: {str(click_err)}")
                
                # Take a full page screenshot
                await page.screenshot(path=screenshot_path, full_page=True)
                await send_log_fn("INFO", f"Screenshot captured at sandbox/screenshots/iteration_{iteration}.png")
                
            except Exception as e:
                await send_log_fn("ERROR", f"Browser navigation or capture failed: {str(e)}")
                page_errors.append(f"CAPTURE_FAILED: {str(e)}")
            finally:
                await browser.close()
                
        # Read screenshot back as base64
        screenshot_b64 = ""
        if os.path.exists(screenshot_path):
            file_size = os.path.getsize(screenshot_path)
            if file_size > 0:
                with open(screenshot_path, "rb") as image_file:
                    screenshot_b64 = base64.b64encode(image_file.read()).decode("utf-8")
            else:
                await send_log_fn("WARNING", f"Screenshot file iteration_{iteration}.png is empty (0 bytes).")
        else:
            await send_log_fn("WARNING", f"Screenshot file iteration_{iteration}.png was not created.")
                
        all_logs = console_messages + page_errors
        return screenshot_b64, all_logs

    def apply_replacements(self, code: str, replacements: list[ReplacementChunk]) -> str:
        soup = BeautifulSoup(code, "html.parser")
        for rep in replacements:
            selector = rep.selector.strip()
            content = rep.replacement_content
            
            # Find element
            element = soup.select_one(selector)
            if element:
                if selector in ("style", "script") or element.name in ("style", "script"):
                    element.string = content
                else:
                    element.clear()
                    new_nodes = BeautifulSoup(content, "html.parser")
                    element.append(new_nodes)
            else:
                logger.warning(f"Selector '{selector}' not found in HTML. Skipping replacement.")
        return str(soup)

    async def run_healer_step(self, prompt: str, code: str, screenshot_b64: str, logs: list[str], iteration: int, send_log_fn) -> tuple[bool, str, str]:
        """
        Sends code + screenshot + logs to Gemini and returns (is_perfect, feedback, healed_code)
        """
        if not screenshot_b64:
            raise ValueError(
                "Browser audit failed: Playwright could not capture a valid screenshot of the sandbox page. "
                "This usually happens when navigation times out or the server host resolves incorrectly (e.g., localhost vs 127.0.0.1)."
            )

        await send_log_fn("INFO", f"Analyzing page visuals and console output using Gemini Multimodal...")
        
        logs_str = "\n".join(logs) if logs else "No console errors detected."
        
        # Construct content elements
        contents = [
            types.Part.from_bytes(
                data=base64.b64decode(screenshot_b64),
                mime_type="image/png"
            ),
            f"Original Prompt: {prompt}\n\n"
            f"Current HTML Code:\n```html\n{code}\n```\n\n"
            f"Browser Logs & Console Output:\n{logs_str}\n\n"
            "Instructions:\n"
            "1. Inspect the screenshot of the rendered web page. Assess the aesthetic quality: alignment, typography, colors, layout gaps, mobile responsiveness, and overall 'wow' factor.\n"
            "2. Read the browser logs. If there are exceptions, JS crashes, or Tailwind CDN warnings, they must be resolved.\n"
            "3. If the page matches the prompt, is visual perfection, is fully functional, and has zero console errors, set 'is_perfect' to true and leave 'replacements' empty.\n"
            "4. If there are any flaws, design deficiencies, alignment issues, or console errors, write a detailed visual critique in 'feedback' and return a list of specific DOM replacements in 'replacements' to fix the issues. You can replace the entire CSS block with selector 'style', the entire JS logic with selector 'script', or specific HTML containers (e.g. '#dashboard-grid', '#music-player'). Provide only the inner content for these tags/elements. Do not wrap custom styles in <style> tags or scripts in <script> tags when replacing them—provide raw CSS/JS string.\n"
            "5. You must format your output as a single JSON object matching this structure exactly (do not output any text other than this JSON):\n"
            "{\n"
            "  \"is_perfect\": false,\n"
            "  \"feedback\": \"Your detailed critique of the visual design...\",\n"
            "  \"replacements\": [\n"
            "    {\n"
            "      \"selector\": \"style\",\n"
            "      \"replacement_content\": \"/* raw custom CSS code... */\"\n"
            "    },\n"
            "    {\n"
            "      \"selector\": \"#dashboard-header\",\n"
            "      \"replacement_content\": \"<!-- new inner HTML content... -->\"\n"
            "    }\n"
            "  ]\n"
            "}"
        ]
        
        try:
            # We call gemini-2.5-flash and request JSON output without constrained schema to avoid truncation issues
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2, # Low temperature for precise code edits and corrections
                    max_output_tokens=8192,
                )
            )
            
            try:
                result_json = json.loads(response.text)
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON decode failed on Gemini output: {str(json_err)}. Text: {response.text}")
                raise ValueError(
                    "The visual critic response was truncated by the model's output limit. "
                    "The page code is likely too large. Try a simpler prompt or keep the design more lightweight."
                )
                
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
                with open(self.code_path, "w", encoding="utf-8") as f:
                    f.write(healed_code)
                await send_log_fn("INFO", f"Code changes applied for iteration {iteration} ({len(replacements)} components healed).")
            
            return is_perfect, feedback, healed_code
            
        except Exception as e:
            await send_log_fn("ERROR", f"Failed to run visual healing critique: {str(e)}")
            raise e
