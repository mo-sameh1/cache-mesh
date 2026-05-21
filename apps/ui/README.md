# CacheMesh Console

This is a static browser dashboard for the distributed CacheMesh deployment.

Open it after the services are running. You can either open
`apps/ui/index.html` directly in a browser or serve the folder locally:

```powershell
cd apps\ui
python -m http.server 3000
```

If you serve it locally, open:

```text
http://localhost:3000
```

On first load, go to the **Settings** tab and set the gateway, name-service,
inference, and replica URLs for your current three-machine deployment.

The console supports:

- gateway prompt queries
- hit/miss display and selected replica display
- direct reads from all replicas
- name-service membership polling
- per-replica health polling
- per-replica `/coordination` polling
- write token visibility
- fault injection through the gateway
- editable replica endpoint settings
- environment target preview for the three-machine setup
- snapshot/replay API calls
