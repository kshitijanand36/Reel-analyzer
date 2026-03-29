import asyncio
import os

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.models import ScrapeRequest, ScrapeResponse
from backend.cookies import load_cookies
from backend.scraper import scrape_reel

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load cookies once at startup
_cookies: list[dict] = []
try:
    _cookies = load_cookies()
    print(f"Loaded {len(_cookies)} Instagram cookies")
except FileNotFoundError:
    print("WARNING: cookies.txt not found. Instagram scraping will likely fail.")


@app.post("/api/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest):
    url = req.url.strip()
    if "instagram.com" not in url:
        raise HTTPException(status_code=400, detail="Please provide a valid Instagram URL")

    # Run Playwright in a separate event loop/thread to avoid conflicts with uvicorn's loop
    loop = asyncio.new_event_loop()
    try:
        result = await asyncio.to_thread(loop.run_until_complete, scrape_reel(url, _cookies))
    finally:
        loop.close()

    if result.get("error") and not result.get("caption") and not result.get("comments"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# Serve React production build if it exists
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(_frontend_dist, "index.html"))
