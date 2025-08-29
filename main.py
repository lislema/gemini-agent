import os
import json
from typing import List, Optional, AsyncGenerator
from weakref import ref

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Google Gen AI SDK
import google.genai as genai
from google.genai import types

# --- Bootstrap ---
load_dotenv()  # load .env if present

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing GOOGLE_API_KEY. Set it in your environment or .env file.")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # good default for latency

# Construct the client once (reuse connection pool)
client = genai.Client(api_key=API_KEY)

app = FastAPI(
    title="Local Gemini Agent",
    version="1.0.0",
    description="FastAPI microservice that routes requests to Gemini 2.5 via Google Gen AI SDK.",
)

# --------- Gemini config  ---------




# ----------- Helpers ---------

def _out_text(resp) -> str:
    """
    Extract plain text from a google-genai GenerateContentResponse (v1.31.0 safe).
    Avoids .to_dict(); handles both object and dict-like fields.
    """
    # 1) Direct convenience attrs (some SDK builds expose these)
    for attr in ("text", "output_text"):
        val = getattr(resp, attr, None)
        if isinstance(val, str) and val.strip():
            return val

    # 2) Walk candidates -> content -> parts -> text
    candidates = getattr(resp, "candidates", None)
    if candidates is None and isinstance(resp, dict):
        candidates = resp.get("candidates")

    if candidates:
        texts = []
        for cand in candidates:
            content = getattr(cand, "content", None) if not isinstance(cand, dict) else cand.get("content")
            if not content:
                continue
            parts = getattr(content, "parts", None) if not isinstance(content, dict) else content.get("parts")
            if not parts:
                continue
            for p in parts:
                t = getattr(p, "text", None) if not isinstance(p, dict) else p.get("text")
                if isinstance(t, str) and t:
                    texts.append(t)
        if texts:
            return "\n".join(texts)

    # 3) Nothing found
    return ""

def _err(detail: str, code: str = "GENERATION_ERROR", status: int = 500):
    """Raise a FastAPI HTTPException in a consistent JSON shape."""
    # Try to surface provider message if present in a JSON tail
    msg = detail
    try:
        import re
        m = re.search(r"\{.*\}$", detail, re.S)
        if m:
            j = json.loads(m.group(0))
            provider_msg = j.get("error", {}).get("message")
            if provider_msg:
                msg = provider_msg
    except Exception:
        pass
    raise HTTPException(status_code=status, detail={"code": code, "message": msg})

def _debug_dump(obj) -> str:
    """Best-effort compact representation without .to_dict()."""
    try:
        # pydantic models in some builds support model_dump()
        md = getattr(obj, "model_dump", None)
        if callable(md):
            return json.dumps(md(), ensure_ascii=False)[:2000]
    except Exception:
        pass
    try:
        # Shallow __dict__ is often enough to see top-level fields
        return json.dumps(getattr(obj, "__dict__", {}), default=str, ensure_ascii=False)[:2000]
    except Exception:
        pass
    # Fallback to repr
    return repr(obj)[:2000]

# --------- Schemas ---------
class PromptRequest(BaseModel):
    prompt: str = Field(..., description="User prompt text.")
    model: Optional[str] = Field(None, description="Override model id (defaults to env or 2.5-flash).")
    system: Optional[str] = Field(None, description="Optional system instruction (mapped into a user message).")
    max_output_tokens: Optional[int] = Field(1024, ge=1, le=8192)
    temperature: Optional[float] = Field(0.3, ge=0.0, le=2.0)

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|model)$")  # Gemini 1.31.0 accepts only user|model
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="Chronological messages (roles: user|model).")
    model: Optional[str] = None
    max_output_tokens: Optional[int] = 1024
    temperature: Optional[float] = 0.3

# --------- Routes ---------
@app.get("/health")
def health():
    return JSONResponse(content={"status": "ok", "version": "1.0.0", "service": "gemini-agent"})

@app.post("/prompt")
def prompt(req: PromptRequest):
    model = req.model or DEFAULT_MODEL
    try:
        contents = []
        if req.system:
            contents.append({"role": "user", "parts": [{"text": f"[System instruction]: {req.system}"}]})
        contents.append({"role": "user", "parts": [{"text": req.prompt}]})

        cfg = types.GenerateContentConfig(
            temperature = req.temperature or 0.3,
            max_output_tokens = req.max_output_tokens or 1024,
            response_modalities = ["TEXT"],
            thinking_config = types.ThinkingConfig(thinking_budget=0),
        )

        resp = client.models.generate_content(
            model=model,
            contents=contents,
            config=cfg,
        )
        return {"model": model, "output": _out_text(resp)}
    except Exception as e:
        _err(str(e))

@app.post("/chat")
def chat(req: ChatRequest):
    model = req.model or DEFAULT_MODEL
    contents = [{"role": m.role, "parts": [{"text": m.content}]} for m in req.messages]
    try:
        cfg = types.GenerateContentConfig(
            temperature = req.temperature or 0.3,
            max_output_tokens = req.max_output_tokens or 1024,
            response_modalities = ["TEXT"],
            thinking_config = types.ThinkingConfig(thinking_budget=0),
        )
        resp = client.models.generate_content(model=model, contents=contents, config=cfg)
        return {"model": model, "output": _out_text(resp)}
    except Exception as e:
        _err(str(e))

# --- Streaming via Server-Sent Events (SSE) ---
@app.post("/stream")
def stream(req: PromptRequest):
    async def event_gen():
        model = req.model or DEFAULT_MODEL
        try:
            contents = []
            if req.system:
                contents.append({"role": "user", "parts": [{"text": f"[System instruction]: {req.system}"}]})
            contents.append({"role": "user", "parts": [{"text": req.prompt}]})

            # No context manager — iterate the generator directly
            final = []
            stream_iter = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    temperature=req.temperature or 0.3,
                    max_output_tokens=req.max_output_tokens or 1024,
                    response_modalities=["TEXT"],
                    thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
                ),
            )

            for chunk in stream_iter:
                delta = getattr(chunk, "text", None)
                if delta:
                    final.append(delta)
                    yield f"data: {json.dumps({'delta': delta})}\n\n".encode("utf-8")

            # done
            yield f"data: {json.dumps({'final': ''.join(final)})}\n\n".encode("utf-8")

        except Exception as e:
            # surface streaming errors to the client
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode("utf-8")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.get("/versions")
def versions():
    import google.genai as _genai
    return {
        "service": "gemini-agent",
        "sdk_version": getattr(_genai, "__version__", "unknown"),
        "model_default": DEFAULT_MODEL,
        "has_models_api": hasattr(client, "models"),
        "env_key_present": bool(API_KEY),
    }

# Optional local run helper:
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)