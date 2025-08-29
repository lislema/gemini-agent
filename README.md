# gemini-agent

FastAPI microservice that exposes Gemini 2.5 (via Google GenAI SDK) behind a simple REST API.

The idea is to run the agent in GCP in Kubernetes and to send REST commands to it 

## Features
- `/health` – health check
- `/prompt` – one-shot text generation
- `/chat` – multi-turn chat
- `/stream` – SSE streaming responses

## Run locally
you need to set up your own Gemini Model API key and select the model and place in a .env file 

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## Run with Docker 

Docker is built using multi stage builds 

### Build debug & run 

```bash
docker build --target debug -t gemini-agent:debug .
docker run --rm -p 8080:8080 \
  -e GOOGLE_API_KEY="your-key" \
  -e GEMINI_MODEL="gemini-2.5-flash" \
  gemini-agent:debug
```

### Build production (without command line) & run 

```bash
docker build --target prod  -t gemini-agent:prod .
docker run --rm -p 8080:8080 \
  -e GOOGLE_API_KEY="your-key" \
  -e GEMINI_MODEL="gemini-2.5-flash" \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --name gemini-agent-prod \
  gemini-agent:prod
```

## Test with Curl

### Health check
```bash
curl -s http://localhost:8080/health | jq .
```
### Prompt
```bash
curl -s http://localhost:8080/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Say HELLO twice.","temperature":0.0,"max_output_tokens":10}' | jq .
```

### Stream
```bash
curl -N http://localhost:8080/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Write a short haiku about Kubernetes."}'
```

### Start the shell
```bash
docker exec -it gemini-agent-debug sh
```
