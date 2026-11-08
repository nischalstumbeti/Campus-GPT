"""Run the Campus-GPT backend server."""
import uvicorn

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "8002"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
