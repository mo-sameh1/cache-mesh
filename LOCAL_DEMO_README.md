# CacheMesh Fully Local Demo

This guide runs the whole CacheMesh distributed flow on one laptop with Docker Desktop:

```text
gateway -> replica read miss -> stub inference -> replica write -> peer replication -> later cache hit
```

The local demo simulates four logical machines using four Docker Compose projects:

```text
cachemesh-core       name-service + gateway + inference-adapter
cachemesh-replica-a replica-a + qdrant
cachemesh-replica-b replica-b + qdrant
cachemesh-replica-c replica-c + qdrant
```

The local demo can run in two inference modes:

```text
stub  fast fake inference for reliable demos
real  Hugging Face Transformers inference with a real local model
```

The replicas use deterministic demo embeddings in both local modes, so the replica side avoids downloading `sentence-transformers`. In `real` mode, only the inference adapter uses the heavy model runtime.

## 1. Install Docker Desktop

Install Docker Desktop before running the project.

Windows:

1. Download Docker Desktop from `https://www.docker.com/products/docker-desktop/`.
2. Install it with the WSL 2 backend enabled.
3. Restart if the installer asks.
4. Open Docker Desktop and wait until it says Docker is running.
5. Open PowerShell and verify:

```powershell
docker version
docker compose version
```

macOS:

1. Download Docker Desktop from `https://www.docker.com/products/docker-desktop/`.
2. Drag Docker into Applications.
3. Open Docker Desktop and wait until it says Docker is running.
4. Open Terminal and verify:

```bash
docker version
docker compose version
```

## 2. Open The Repo Root

Run every command from the repo root.

For this machine:

```powershell
cd "D:\EUI Seniors\Spring\Distributed Systems\cache-mesh"
```

You should see the Compose file here:

```powershell
Get-ChildItem docker-compose.yml
```

## 3. Start From A Clean Demo State

This removes only the local CacheMesh demo Compose projects. It does not run `docker system prune`, and it does not delete unrelated Docker images or containers.

```powershell
docker compose -p cachemesh-core down -v --remove-orphans
docker compose -p cachemesh-replica-a down -v --remove-orphans
docker compose -p cachemesh-replica-b down -v --remove-orphans
docker compose -p cachemesh-replica-c down -v --remove-orphans
```

The demo replicas use bind-mounted Qdrant folders under `.docker/demo-replica-*`. If you have run the demo before and want a totally empty cache, remove those folders too.

Try PowerShell first:

```powershell
Remove-Item -Recurse -Force .\.docker\demo-replica-a, .\.docker\demo-replica-b, .\.docker\demo-replica-c -ErrorAction SilentlyContinue
```

If Windows refuses because Qdrant created Linux-owned files, use Docker to remove only those demo folders:

```powershell
docker run --rm -v "${PWD}:/work" cachemesh-core-name-service sh -c "rm -rf /work/.docker/demo-replica-a /work/.docker/demo-replica-b /work/.docker/demo-replica-c"
```

If the `cachemesh-core-name-service` image does not exist yet, skip that command on the first run. The folders will usually not exist before the first demo.

## 4. Choose Inference Mode

Use `stub` mode for normal demos and rehearsals:

```powershell
.\scripts\start-local-demo.ps1 -InferenceMode stub
```

Use `real` mode only when you intentionally want the inference adapter to load a real Hugging Face model:

```powershell
.\scripts\start-local-demo.ps1 -InferenceMode real
```

Real mode uses:

```env
INFERENCE_BACKEND=hf_transformers
INFERENCE_MODEL_ID=Qwen/Qwen2.5-7B-Instruct
INFERENCE_DOCKERFILE=Dockerfile.inference
```

Real mode can take a long time on first run. It may download several gigabytes of dependencies/model files and may require a strong GPU or a lot of RAM. If Docker logs show the inference adapter as `degraded`, the distributed system can still start, but real inference is not ready yet.

If PowerShell blocks script execution, run this once in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then rerun the script.

## 5. Manual Start: Core Services

The script above is recommended. If you prefer manual commands, start name service, gateway, and stub inference:

Start name service, gateway, and stub inference:

```powershell
docker compose --env-file .env.demo-core -p cachemesh-core up -d --build
```

For real inference, use:

```powershell
docker compose --env-file .env.demo-core.real -p cachemesh-core up -d --build
```

Expected result:

```text
cachemesh-core-name-service-1        running on localhost:8100
cachemesh-core-gateway-1             running on localhost:8000
cachemesh-core-inference-adapter-1   running on localhost:8050
```

## 6. Manual Start: Three Replicas

You can run these in the same terminal, one after another:

```powershell
docker compose --env-file .env.demo-replica-a -p cachemesh-replica-a up -d --build
docker compose --env-file .env.demo-replica-b -p cachemesh-replica-b up -d --build
docker compose --env-file .env.demo-replica-c -p cachemesh-replica-c up -d --build
```

Expected ports:

```text
replica-a: localhost:8201, qdrant: localhost:6334
replica-b: localhost:8202, qdrant: localhost:6335
replica-c: localhost:8203, qdrant: localhost:6336
```

## 7. Verify The System Is Up

Check the containers:

```powershell
docker ps --filter name=cachemesh --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Check service health:

```powershell
curl.exe http://localhost:8100/health
curl.exe http://localhost:8050/health
curl.exe http://localhost:8000/health
curl.exe http://localhost:8201/health
curl.exe http://localhost:8202/health
curl.exe http://localhost:8203/health
```

Expected behavior in `stub` mode:

```text
name-service status: ok
inference-adapter status: ok, detail mentions stub backend
gateway status: ok
replica-a status: ok
replica-b status: ok
replica-c status: ok
```

Check membership:

```powershell
curl.exe http://localhost:8100/members
```

Expected behavior:

```text
members contains replica-a, replica-b, and replica-c
all three replicas are healthy
```

The order may vary. That is fine.

In `real` mode, check inference health carefully:

```powershell
curl.exe http://localhost:8050/health
```

Expected real-mode success:

```text
inference-adapter status: ok
detail mentions HF transformers runtime is ready
```

If it says `degraded`, inspect logs:

```powershell
docker compose --env-file .env.demo-core.real -p cachemesh-core logs -f inference-adapter
```

## 8. Use The Demo Console

The browser dashboard lives in `apps/ui`.

Option A: open the HTML file directly:

```text
apps/ui/index.html
```

Option B: serve it on localhost:

```powershell
cd apps\ui
python -m http.server 3000
```

Then open:

```text
http://localhost:3000
```

The console can submit prompts through the gateway, show cache hit/miss status, show the selected replica, poll name-service membership, poll per-replica `/coordination`, run direct reads against all replicas, call fault injection, and show raw JSON evidence for the demo.

## 9. Run The Demo Query

The browser URL `http://localhost:8000/cache/query` is not enough by itself because `/cache/query` is a POST endpoint. Use PowerShell or curl to send JSON.

PowerShell version:

```powershell
$body = @{
  prompt = 'What is distributed caching?'
  model_id = 'demo-model'
  semantic_enabled = $true
} | ConvertTo-Json -Compress

Invoke-RestMethod -Method Post -Uri http://localhost:8000/cache/query -ContentType 'application/json' -Body $body
```

Expected first request in `stub` mode:

```text
hit: false
response_text: stub inference response
cache_status: miss_generated
detail: cache miss generated through inference and write was attempted successfully
```

In `real` mode, `response_text` should be generated by the configured Hugging Face model instead of the fixed stub text.

The selected replica may be `replica-a`, `replica-b`, or `replica-c`. That is fine.

Run the same command again.

Expected second request:

```text
hit: true
response_text: stub inference response
cache_status: hit
score: 1.0
detail: cache hit returned by replica
```

This proves the second request did not need inference.

## 10. Prove Replication Worked

After the first successful query, all three replicas should have the cached response.

```powershell
$body = @{
  prompt = 'What is distributed caching?'
  model_id = 'demo-model'
  semantic_enabled = $true
} | ConvertTo-Json -Compress

Invoke-RestMethod -Method Post -Uri http://localhost:8201/cache/read -ContentType 'application/json' -Body $body
Invoke-RestMethod -Method Post -Uri http://localhost:8202/cache/read -ContentType 'application/json' -Body $body
Invoke-RestMethod -Method Post -Uri http://localhost:8203/cache/read -ContentType 'application/json' -Body $body
```

Expected behavior from all three in `stub` mode:

```text
hit: true
response_text: stub inference response
replica_id: replica-a / replica-b / replica-c
score: 1.0
```

In `real` mode, all three replicas should return the real generated response text from the first query.

## 11. Shut Down After The Demo

Stop the local demo:

```powershell
.\scripts\stop-local-demo.ps1
```

Manual equivalent:

```powershell
docker compose -p cachemesh-core down
docker compose -p cachemesh-replica-a down
docker compose -p cachemesh-replica-b down
docker compose -p cachemesh-replica-c down
```

If you also want to delete the cached demo data, use the clean-state commands in section 3.
