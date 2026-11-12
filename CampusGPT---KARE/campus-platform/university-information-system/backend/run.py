import os

import uvicorn


if __name__ == "__main__":
    # reload off by default — Windows + SQLite + reload often leaves a hung :8000 process
    reload = os.getenv("UIS_RELOAD", "0") == "1"
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)
