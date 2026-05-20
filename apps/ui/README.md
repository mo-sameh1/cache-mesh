# CacheMesh Demo Console

This is a static browser dashboard for the CacheMesh demo.

## Clean Start

Run this from PowerShell when you want to stop any current local demo and clear the cached demo data:

```powershell
cd "D:\EUI Seniors\Spring\Distributed Systems\cache-mesh"
.\scripts\clean-local-demo.ps1
```

This removes the demo containers and persisted local Qdrant state, so the next run starts with an empty cache.

Avoid this unless you intentionally want to delete unused Docker images, build cache, and volumes:

```powershell
.\scripts\clean-local-demo.ps1 -PruneDockerSystem
```

That can make the next real demo slow again because Docker may need to rebuild images and redownload heavy dependencies.

## Path 1: Fast Stub Demo

Use this for the smoothest live demo. It uses fake inference, but it still shows the full distributed flow: gateway, replica selection, cache miss, write, replication, later cache hit, health, faults, and write-token behavior.

Terminal 1:

```powershell
cd "D:\EUI Seniors\Spring\Distributed Systems\cache-mesh"
.\scripts\start-local-demo.ps1 -InferenceMode stub
```

Terminal 2, for the dashboard:

```powershell
cd "D:\EUI Seniors\Spring\Distributed Systems\cache-mesh\apps\ui"
python -m http.server 3000
```

Open:

```text
http://localhost:3000
```

Use these query settings:

```text
Model ID: demo-model
Semantic lookup: checked
```

Expected behavior:

- First prompt: cache miss, stub inference response, write to a selected replica, then replication to the other replicas.
- Same prompt again: cache hit.
- Failure buttons still work.
- Overview shows health, membership, selected replica, and write-token behavior.

## Path 2: Real Inference + Real Semantic Cache

Use this when you want the heavier demo with real local LLM inference and real sentence-transformer semantic matching.

Terminal 1:

```powershell
cd "D:\EUI Seniors\Spring\Distributed Systems\cache-mesh"
.\scripts\start-local-demo.ps1 -InferenceMode real -RealModel small -SemanticMode sentence-transformers
```

First startup can take several minutes because it downloads and loads:

- `Qwen/Qwen2.5-0.5B-Instruct`
- `sentence-transformers/all-MiniLM-L6-v2`
- CPU PyTorch and related Python packages, if the semantic image has not been built yet

Wait until these checks are healthy:

```powershell
curl.exe http://localhost:8050/health
curl.exe http://localhost:8100/members
curl.exe http://localhost:8201/health
curl.exe http://localhost:8202/health
curl.exe http://localhost:8203/health
```

Terminal 2, for the dashboard:

```powershell
cd "D:\EUI Seniors\Spring\Distributed Systems\cache-mesh\apps\ui"
python -m http.server 3000
```

Open:

```text
http://localhost:3000
```

Use these query settings:

```text
Model ID: Qwen/Qwen2.5-0.5B-Instruct
Semantic lookup: checked
```

Good semantic-cache test:

```text
What is write-through caching?
```

Then:

```text
Explain write-through cache.
```

Expected behavior:

- First prompt: miss, real inference answer, write, replication.
- Second prompt: semantic hit with a high score.
- Different topic: miss.

## Stop Or Restart

Normal stop:

```powershell
cd "D:\EUI Seniors\Spring\Distributed Systems\cache-mesh"
.\scripts\stop-local-demo.ps1
```

Full clean reset:

```powershell
cd "D:\EUI Seniors\Spring\Distributed Systems\cache-mesh"
.\scripts\clean-local-demo.ps1
```

Restart without rebuilding images:

```powershell
.\scripts\start-local-demo.ps1 -InferenceMode stub -NoBuild
```

or:

```powershell
.\scripts\start-local-demo.ps1 -InferenceMode real -RealModel small -SemanticMode sentence-transformers -NoBuild
```

`-NoBuild` avoids Docker image rebuilds. It may still take time to load models into memory, but it should not redownload everything if the image and model cache are still present.

## Avoiding Slow Redownloads

These commands can force long rebuilds or redownloads:

```powershell
.\scripts\clean-local-demo.ps1 -PruneDockerSystem
docker system prune -a --volumes -f
docker builder prune -a
```

They can remove Docker images, build cache, and unused volumes. Avoid them before a demo unless you specifically want a deep Docker cleanup.

For normal cleanup, use:

```powershell
.\scripts\clean-local-demo.ps1
```

For normal stopping, use:

```powershell
.\scripts\stop-local-demo.ps1
```

## Dashboard Features

The console supports:

- gateway prompt queries
- hit/miss display and selected replica display
- direct reads from all replicas
- name-service membership polling
- per-replica health polling
- per-replica `/coordination` polling
- write token visibility
- fault injection through the gateway
- local endpoint presets
- editable three-laptop endpoint settings
- snapshot/replay API calls
