import json
import os
import re
import shutil
import subprocess
import tempfile

from dotenv import load_dotenv
load_dotenv()

from google import genai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))


class ReelRequest(BaseModel):
    url: str


def fetch_reel_info_with_ytdlp(url: str, tmpdir: str) -> dict:
    """Use yt-dlp to download video AND extract metadata (caption, uploader, etc.)."""
    output_path = os.path.join(tmpdir, "reel.mp4")
    info_path = os.path.join(tmpdir, "info.json")

    cookies_file = os.path.join(os.path.dirname(__file__), "cookies.txt")

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--cookies", cookies_file,
        "-f", "mp4/best",
        "-o", output_path,
        "--write-info-json",
        "--no-write-playlist-metafiles",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    # Try to load the info json even if download partially failed
    info = {}
    # yt-dlp writes info json with the video name
    possible_info_files = [
        os.path.join(tmpdir, "reel.info.json"),
        info_path,
    ]
    # Also check for any .info.json file in tmpdir
    for f in os.listdir(tmpdir):
        if f.endswith(".info.json"):
            possible_info_files.insert(0, os.path.join(tmpdir, f))

    for p in possible_info_files:
        if os.path.exists(p):
            with open(p) as f:
                info = json.load(f)
            break

    if not info and result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")

    video_path = output_path if os.path.exists(output_path) else None
    # Sometimes yt-dlp adds extension, check for other files
    if not video_path:
        for f in os.listdir(tmpdir):
            if f.endswith((".mp4", ".webm", ".mkv")) and "info" not in f:
                video_path = os.path.join(tmpdir, f)
                break

    caption = info.get("description", "") or ""
    owner = info.get("uploader", "") or info.get("channel", "") or "unknown"
    # Clean up owner - remove @ prefix if present
    owner = owner.lstrip("@")
    likes = info.get("like_count", 0) or 0
    comment_count = info.get("comment_count", 0) or 0
    upload_date = info.get("upload_date", "")
    if upload_date:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

    # yt-dlp can also extract comments with --write-comments but it's slow
    # We'll extract them separately if needed
    comments = []
    for c in info.get("comments", []) or []:
        comments.append({
            "user": c.get("author", "unknown"),
            "text": c.get("text", ""),
        })
        if len(comments) >= 30:
            break

    return {
        "caption": caption,
        "owner": owner,
        "likes": likes,
        "date": upload_date,
        "comment_count": comment_count,
        "comments": comments,
        "video_path": video_path,
    }


def extract_frames(video_path: str, tmpdir: str, num_frames: int = 6) -> list[str]:
    """Extract evenly-spaced frames from the video using ffmpeg."""
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", video_path,
    ]
    probe = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    frame_paths = []
    for i in range(num_frames):
        timestamp = (duration / (num_frames + 1)) * (i + 1)
        frame_path = os.path.join(tmpdir, f"frame_{i}.jpg")
        cmd = [
            "ffmpeg", "-y", "-ss", str(timestamp),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            frame_path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(frame_path):
            img = Image.open(frame_path)
            if img.width > 720:
                ratio = 720 / img.width
                img = img.resize((720, int(img.height * ratio)), Image.LANCZOS)
                img.save(frame_path, quality=80)
            frame_paths.append(frame_path)

    return frame_paths


def analyze_with_gemini(metadata: dict, frame_paths: list[str]) -> dict:
    """Send everything to Gemini for analysis."""
    comments_text = ""
    if metadata["comments"]:
        comments_text = "\n".join(
            f"  @{c['user']}: {c['text']}" for c in metadata["comments"]
        )
    else:
        comments_text = "  (no comments available)"

    context = f"""Here is the metadata for an Instagram Reel:

**Posted by:** @{metadata['owner']}
**Date:** {metadata['date']}
**Likes:** {metadata['likes']}

**Caption:**
{metadata['caption'] or '(no caption)'}

**Comments (up to 30):**
{comments_text}
"""

    prompt = f"""{context}

Based on the video frames (if provided), caption, and comments above, provide a detailed analysis of this Instagram Reel. Return your response as JSON with these fields:

{{
  "title": "A short descriptive title for the reel (max 10 words)",
  "summary": "A 2-3 sentence summary of what the reel is about",
  "topic": "The main topic/category (e.g., Food, Travel, Comedy, Tech, Fashion, Fitness, Education, etc.)",
  "key_points": ["List of 3-5 key points or takeaways from the reel"],
  "sentiment": "Overall sentiment of the reel and audience reaction (positive/negative/mixed/neutral)",
  "context": "Any additional context that helps understand the reel (trends, references, cultural context)",
  "engagement_summary": "Brief summary of how people are reacting in the comments"
}}

Return ONLY the JSON, no markdown fences."""

    contents = []
    for path in frame_paths:
        with open(path, "rb") as f:
            img_bytes = f.read()
        contents.append(
            genai.types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
        )
    contents.append(prompt)

    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    return json.loads(text)


@app.post("/api/analyze")
async def analyze_reel(req: ReelRequest):
    url = req.url.strip()
    if "instagram.com" not in url:
        raise HTTPException(status_code=400, detail="Please provide a valid Instagram Reel URL")

    tmpdir = tempfile.mkdtemp()
    try:
        # Step 1: Download video + extract metadata via yt-dlp
        try:
            reel_info = fetch_reel_info_with_ytdlp(url, tmpdir)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch reel: {e}")

        # Step 2: Extract frames from video
        frame_paths = []
        if reel_info["video_path"]:
            try:
                frame_paths = extract_frames(reel_info["video_path"], tmpdir)
            except Exception as e:
                print(f"Frame extraction failed (will analyze text only): {e}")

        # Step 3: Analyze with Gemini
        metadata = {
            "caption": reel_info["caption"],
            "owner": reel_info["owner"],
            "likes": reel_info["likes"],
            "date": reel_info["date"],
            "comments": reel_info["comments"],
        }
        analysis = analyze_with_gemini(metadata, frame_paths)

        return {
            "metadata": {
                "owner": reel_info["owner"],
                "likes": reel_info["likes"],
                "date": reel_info["date"],
                "comment_count": reel_info["comment_count"] or len(reel_info["comments"]),
            },
            "analysis": analysis,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
