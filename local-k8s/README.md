# Running Gemini Agent on Minikube

This guide explains how to build, load, and run the **Gemini Agent** inside a local Minikube cluster.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (≥ 4 CPUs, ≥ 6 GB RAM recommended)
- [Minikube](https://minikube.sigs.k8s.io/docs/start/) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/)

---

## 🔧 1. Start Minikube

```bash
minikube start --driver=docker --cpus=4 --memory=6144 --disk-size=20g
```

Verify the cluster is ready:

```bash
kubectl get nodes
kubectl get pods -A
```

---

## 2. Build and Load the Image

### Option A — Build inside Minikube
```bash
eval $(minikube docker-env)
docker build --target prod -t gemini-agent:prod ..
eval $(minikube docker-env -u)
```

### Option B — Build locally and load into Minikube
```bash
docker build --target prod -t gemini-agent:prod ..
minikube image load gemini-agent:prod
```

Verify the image is visible in Minikube:

```bash
minikube ssh -- docker images | grep gemini-agent
```

---

## 3. Create Secrets

Your Gemini API key must be provided as a Kubernetes Secret.

Edit `secret.yaml` (replace with your real key):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: gemini-secrets
  namespace: default
type: Opaque
stringData:
  GOOGLE_API_KEY: "AIza...your_api_key_here"
```

Apply it:

```bash
kubectl apply -f secret.yaml
```

---

## 4. Deploy the Agent

Apply the Deployment manifest:

```bash
kubectl apply -f deployment.yaml
```

Check the pod status:

```bash
kubectl get pods
kubectl describe pod -l app=gemini-agent
```

---

## 5. Expose the Service

### Option A — ClusterIP + Port-Forward
Apply:

```bash
kubectl apply -f service.yaml
```

Port-forward:

```bash
kubectl port-forward svc/gemini-agent 8081:80
```

Test:

```bash
curl -s http://localhost:8081/health | jq .
```

### Option B — NodePort (direct access)
If you prefer, apply `service-nodeport.yaml`:

```bash
kubectl apply -f service-nodeport.yaml
```

Get Minikube IP:

```bash
minikube ip
```

Test:

```bash
curl -s http://$(minikube ip):30080/health | jq .
```

---

## 6. Test the Endpoints

Prompt endpoint:

```bash
curl -s http://localhost:8081/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Give me three bullet points on why agents need guardrails.",
    "system": "You are a concise security architect.",
    "temperature": 0.2,
    "max_output_tokens": 256
  }' | jq .
```

---

## 7. Clean Up

```bash
kubectl delete -f service.yaml
kubectl delete -f deployment.yaml
kubectl delete -f secret.yaml
minikube stop
```

---

Now your **Gemini Agent** is running inside Minikube with full health probes, secrets, and service exposure.
