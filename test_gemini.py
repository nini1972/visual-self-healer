import os
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        return
        
    client = genai.Client(api_key=api_key)
    
    prompt = "a dashboard with a dynamic growth of a plant"
    logs_str = "No console errors detected."
    code = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stellar Journey Dashboard</title>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Inter:wght@300;400;500;700&display=swap" rel="stylesheet">
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* ... styles ... */
    </style>
</head>
<body>
</body>
</html>"""

    # Mimic content structure
    contents = [
        "This is a test prompt",
        f"Original Prompt: {prompt}\n\n"
        f"Current HTML Code:\n```html\n{code}\n```\n\n"
        f"Browser Logs & Console Output:\n{logs_str}\n\n"
        "Instructions:\n"
        "1. Inspect the page visuals.\n"
        "2. Return JSON matching CritiqueResponse schema."
    ]
    
    print("Calling Gemini model...")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents="Hello, this is a test. Please reply with a short JSON containing is_perfect=false, feedback='test', and replacements=[].",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        print("Simple Call Success!")
        print(f"Response: {response.text}")
        
        # Now try to inspect candidate structure
        candidates = response.candidates
        if candidates:
            c = candidates[0]
            print(f"Finish Reason: {c.finish_reason}")
            print(f"Safety Ratings: {c.safety_ratings}")
            
    except Exception as e:
        print(f"Call failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
