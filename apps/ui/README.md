# CacheMesh Demo Console

This is a static browser dashboard for the CacheMesh demo.

Open it after the Docker demo is running:

```powershell
cd "D:\EUI Seniors\Spring\Distributed Systems\cache-mesh"
.\scripts\start-local-demo.ps1 -InferenceMode stub
```

Then either open `apps/ui/index.html` directly in a browser or serve the folder:

```powershell
cd apps\ui
python -m http.server 3000
```

If served locally, open:

```text
http://localhost:3000
```

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
