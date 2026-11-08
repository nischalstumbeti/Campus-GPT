# Campus-GPT (sibling app)

Working Campus-GPT application currently lives at the **repository root** (`../../frontend`, `../../backend`).

## Ports

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3001 |
| Backend / docs | http://localhost:8001 / http://localhost:8001/docs |

```text
CAMPUS_GPT_FRONTEND_URL=http://localhost:3001
CAMPUS_GPT_API_URL=http://localhost:8001
UIS_API_BASE_URL=http://localhost:8000
```

## Separation

- UIS owns institutional data on **:3000 / :8000**
- Campus-GPT talks to UIS only via secure HTTP APIs (`UIS_API_BASE_URL`)
- Never connect Campus-GPT directly to the UIS database
