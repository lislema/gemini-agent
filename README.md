# Gemini Agent (FastAPI + Docker)

FastAPI microservice exposing **Google Gemini models** (via the `google-genai` SDK) behind a simple REST interface.

- `/health` → health check  
- `/prompt` → one-shot text generation  
- `/chat` → multi-turn conversation  
- `/stream` → SSE streaming of incremental output  

---

## Features
- Simple REST wrapper around Google Gemini (`gemini-2.5-flash`, etc).  
- Supports system instructions and multi-turn conversations.  
- Secure, multi-stage Docker build (`debug` and `prod` targets).  
- `.env` file for API key and default model.  

---

## Project Structure
```
.
├── main.py          # FastAPI app
├── requirements.txt # Python dependencies
├── Dockerfile       # Multi-stage build (builder, debug, prod)
├── .env             # Local environment variables (ignored by git)
├── .dockerignore
└── .gitignore
```

---

## Environment Variables

Create a `.env` file in the project root:

```dotenv
# Google API key (get from https://aistudio.google.com/app/apikey)
GOOGLE_API_KEY=AIza...your_google_key_here

# Default Gemini model
# Options include:
#   gemini-2.5-flash   (fast, low latency, great default)
#   gemini-1.5-pro     (larger context, slower, more accurate)
GEMINI_MODEL=gemini-2.5-flash
```

⚠️ `.env` is ignored via `.gitignore` — never commit real keys.  
Commit a `.env.example` with placeholders if needed.

---

## Dependencies

`requirements.txt`:

```txt
fastapi==0.112.2
uvicorn==0.30.6
pydantic==2.8.2
python-dotenv==1.0.1
google-genai==1.31.0
```

---

## Docker Setup

Multi-stage Dockerfile:
- **builder** → installs deps into `/app/site-packages`
- **debug** → Chainguard base with shell/tools (~700 MB)
- **prod** → Chainguard minimal runtime (~80 MB, secure)

### Build Debug
```bash
docker build --target debug -t gemini-agent:debug .
```

### Run Debug
```bash
docker run --rm -p 8080:8080   --env-file .env   --cap-drop ALL --security-opt no-new-privileges   --name gemini-agent-debug   gemini-agent:debug
```

### Build Prod
```bash
docker build --target prod -t gemini-agent:prod .
```

### Run Prod (secure, non-root, read-only)
```bash
docker run --rm -p 8080:8080   --env-file .env   --read-only   --cap-drop ALL   --security-opt no-new-privileges   --tmpfs /tmp:rw,noexec,nosuid,size=16m   --name gemini-agent-prod   gemini-agent:prod
```

---

## Testing with `curl`

### Health
```bash
curl -s http://localhost:8080/health | jq .
```

### Prompt
```bash
curl -s http://localhost:8080/prompt   -H "Content-Type: application/json"   -d '{
    "prompt": "Give me three bullet points on why agents need guardrails.",
    "system": "You are a concise security architect.",
    "temperature": 0.2,
    "max_output_tokens": 256
  }' | jq .
```

### Chat
```bash
curl -s http://localhost:8080/chat   -H "Content-Type: application/json"   -d '{
    "messages": [
      {"role": "system", "content": "You are a concise API architect."},
      {"role": "user", "content": "What is an API gateway?"},
      {"role": "model", "content": "It manages, secures, and routes API traffic."},
      {"role": "user", "content": "Name two benefits of putting one in front of LLMs."}
    ],
    "temperature": 0.2,
    "max_output_tokens": 180
  }' | jq .
```

### Stream (SSE)
```bash
curl -N http://localhost:8080/stream   -H "Content-Type: application/json"   -d '{"prompt":"Write a short poem about GKE and API gateways."}'
```

---

## Image Size & Security

Check image sizes:
```bash
docker images | grep gemini-agent
```

Inspect CVEs (with [Trivy](https://github.com/aquasecurity/trivy)):
```bash
trivy image --severity HIGH,CRITICAL gemini-agent:prod
```

---

## 📌 Notes
- Default model can be overridden per-request in `/prompt` and `/chat`.  
- Debug image is large but useful for troubleshooting; prod image is small & hardened.  
- SSE endpoint (`/stream`) streams incremental chunks and the final response.
