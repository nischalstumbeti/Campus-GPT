import os

import uvicorn


if __name__ == "__main__":
    # reload off by default — Windows + SQLite + reload often leaves a hung :8000 process
    reload = os.getenv("UIS_RELOAD", "0") == "1"
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload)
