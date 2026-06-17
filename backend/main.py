import os
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Load env variables (for local GEMINI_API_KEY)
load_dotenv()

from agent import VisualSelfHealerAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auraheal")

app = FastAPI(title="AuraHeal AI Backend")

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SANDBOX_DIR = os.path.join(BASE_DIR, "sandbox")
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

os.makedirs(SANDBOX_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Mount static files
app.mount("/sandbox", StaticFiles(directory=SANDBOX_DIR), name="sandbox")
# Mount frontend
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

@app.get("/")
async def read_root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted.")
    
    async def send_log_fn(level: str, text: str, **kwargs):
        event_types = {"CODE_UPDATE", "AUDIT_RESULT", "HEAL_RESULT"}
        payload = {
            "type": level if level in event_types else "log",
            "level": level,
            "text": text,
        }
        payload.update(kwargs)
        try:
            await websocket.send_json(payload)
        except Exception as ws_err:
            logger.error(f"WebSocket send failed: {str(ws_err)}")

    try:
        while True:
            # Expecting JSON request from frontend
            # Format: { "action": "start", "prompt": "...", "apiKey": "...", "maxIterations": 3 }
            data = await websocket.receive_text()
            request = json.loads(data)
            
            action = request.get("action")
            if action != "start":
                await send_log_fn("WARNING", f"Unknown action received: {action}")
                continue
                
            prompt = request.get("prompt")
            api_key = request.get("apiKey") or os.getenv("GEMINI_API_KEY")
            max_iterations = int(request.get("maxIterations", 4))
            
            if not prompt:
                await send_log_fn("ERROR", "No prompt provided.")
                continue
                
            if not api_key:
                await send_log_fn("ERROR", "No Gemini API Key found in environment or configuration.")
                continue
            
            await send_log_fn("INFO", "Initializing visual self-healer agent...")
            
            # Since uvicorn runs the backend, we fetch the server address dynamically, or default to 127.0.0.1:8500
            # Playwright will query this to capture screenshots
            server_url = "http://127.0.0.1:8500"
            agent = VisualSelfHealerAgent(api_key=api_key, sandbox_dir=SANDBOX_DIR, server_url=server_url)
            
            # Start the self-healing loop
            try:
                # Iteration 0: Initial Code Generation
                await send_log_fn("STATUS", "Generating initial webpage...")
                code = await agent.generate_initial_code(prompt, send_log_fn)
                
                # Stream initial code
                await send_log_fn("CODE_UPDATE", "Initial code generated.", code=code, iteration=0)
                
                is_perfect = False
                iteration = 1
                
                while not is_perfect and iteration <= max_iterations:
                    await send_log_fn("STATUS", f"Auditing webpage layout (Iteration {iteration})...")
                    
                    # Audit (runs Playwright screenshot and console logs)
                    screenshot_b64, logs = await agent.audit_sandbox(iteration, send_log_fn)
                    
                    # Stream screenshot & logs to client
                    await send_log_fn(
                        "AUDIT_RESULT", 
                        f"Audit complete for iteration {iteration}.",
                        screenshot=screenshot_b64,
                        logs=logs,
                        iteration=iteration
                    )
                    
                    # Run Healer step (Critique + Code fix)
                    await send_log_fn("STATUS", f"Performing visual critiquing and healing (Iteration {iteration})...")
                    is_perfect, feedback, code = await agent.run_healer_step(
                        prompt, code, screenshot_b64, logs, iteration, send_log_fn
                    )
                    
                    await send_log_fn(
                        "HEAL_RESULT",
                        f"Healer critique complete for iteration {iteration}.",
                        feedback=feedback,
                        is_perfect=is_perfect,
                        code=code,
                        iteration=iteration
                    )
                    
                    if is_perfect:
                        await send_log_fn("SUCCESS", f"UI has been successfully healed and verified in {iteration} iteration(s)!")
                        break
                        
                    iteration += 1
                    
                if not is_perfect:
                    await send_log_fn("WARNING", f"Self-healing complete, but reached maximum iterations ({max_iterations}) without matching perfection.")
                    
            except Exception as loop_err:
                logger.error(f"Agent loop error: {str(loop_err)}", exc_info=True)
                await send_log_fn("ERROR", f"Agent execution crashed: {str(loop_err)}")
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
