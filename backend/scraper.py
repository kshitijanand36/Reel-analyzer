import asyncio
import json
import re
from playwright.async_api import async_playwright

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _parse_og_description(desc: str) -> dict:
    """Parse the og:description which has format:
    '1M likes, 849 comments - user on January 21, 2026: "caption text"'
    """
    result = {"likes": None, "comment_count": None, "date": None, "caption": None}

    # Extract likes
    likes_match = re.search(r"([\d,.]+[KMB]?)\s*likes?", desc, re.IGNORECASE)
    if likes_match:
        likes_str = likes_match.group(1).replace(",", "")
        multiplier = 1
        if likes_str.endswith("K"):
            multiplier = 1000
            likes_str = likes_str[:-1]
        elif likes_str.endswith("M"):
            multiplier = 1_000_000
            likes_str = likes_str[:-1]
        elif likes_str.endswith("B"):
            multiplier = 1_000_000_000
            likes_str = likes_str[:-1]
        try:
            result["likes"] = int(float(likes_str) * multiplier)
        except ValueError:
            pass

    # Extract comment count
    comments_match = re.search(r"([\d,.]+[KMB]?)\s*comments?", desc, re.IGNORECASE)
    if comments_match:
        count_str = comments_match.group(1).replace(",", "")
        multiplier = 1
        if count_str.endswith("K"):
            multiplier = 1000
            count_str = count_str[:-1]
        elif count_str.endswith("M"):
            multiplier = 1_000_000
            count_str = count_str[:-1]
        try:
            result["comment_count"] = int(float(count_str) * multiplier)
        except ValueError:
            pass

    # Extract caption (inside quotes after the date)
    caption_match = re.search(r':\s*["\u201c](.+?)["\u201d]\.?\s*$', desc, re.DOTALL)
    if caption_match:
        result["caption"] = caption_match.group(1).strip()

    # Extract date
    date_match = re.search(
        r"on\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})",
        desc,
    )
    if date_match:
        result["date"] = f"{date_match.group(1)} {date_match.group(2)}, {date_match.group(3)}"

    return result


async def scrape_reel(url: str, cookies: list[dict]) -> dict:
    """Scrape an Instagram reel page for metadata and comments."""
    result = {
        "caption": None,
        "geotags": [],
        "comments": [],
        "owner": None,
        "likes": None,
        "date": None,
        "error": None,
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()

        try:
            # Intercept API responses to capture media ID for comments
            media_id = None
            shortcode = None

            async def capture_response(response):
                nonlocal media_id
                if "graphql" not in response.url and "api/v1" not in response.url:
                    return
                try:
                    body = await response.json()
                    body_str = json.dumps(body)
                    if shortcode and shortcode in body_str:
                        # Try to find media_id / pk
                        _find_media_id(body, shortcode)
                except Exception:
                    pass

            def _find_media_id(obj, sc, depth=0):
                nonlocal media_id
                if media_id or depth > 8:
                    return
                if isinstance(obj, dict):
                    if obj.get("code") == sc and ("pk" in obj or "id" in obj):
                        media_id = str(obj.get("pk") or obj.get("id"))
                    for v in obj.values():
                        _find_media_id(v, sc, depth + 1)
                elif isinstance(obj, list):
                    for item in obj[:20]:
                        _find_media_id(item, sc, depth + 1)

            page.on("response", capture_response)

            # Extract shortcode from URL
            sc_match = re.search(r"/reel(?:s)?/([A-Za-z0-9_-]+)", url)
            if sc_match:
                shortcode = sc_match.group(1)

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            # --- Check for login wall ---
            login_form = await page.query_selector('form[id="loginForm"]')
            if login_form:
                result["error"] = "Login required. Please refresh your cookies.txt"
                return result

            # --- Extract from meta tags (most reliable) ---
            og_title = await _get_meta(page, 'meta[property="og:title"]')
            og_desc = await _get_meta(page, 'meta[property="og:description"]')

            # Owner from og:title
            if og_title:
                for prefix in ["Video by ", "Reel by "]:
                    if og_title.startswith(prefix):
                        result["owner"] = og_title[len(prefix):].strip()
                        break
                if not result["owner"] and " on Instagram" in og_title:
                    result["owner"] = og_title.split(" on Instagram")[0].strip()

            # Parse og:description for likes, date, caption
            if og_desc:
                parsed = _parse_og_description(og_desc)
                result["caption"] = parsed["caption"]
                result["likes"] = parsed["likes"]
                result["date"] = parsed["date"]

            # --- Geotags / Location ---
            location_els = await page.query_selector_all('a[href*="/explore/locations/"]')
            for el in location_els:
                text = (await el.inner_text()).strip()
                if text and text not in result["geotags"]:
                    result["geotags"].append(text)

            # --- Comments via Instagram API ---
            # We need the media ID. Try to extract from the page source
            if not media_id:
                media_id = await _extract_media_id_from_page(page, shortcode)

            if media_id:
                comments = await _fetch_comments_via_api(context, media_id, max_comments=20)
                result["comments"] = comments

        except Exception as e:
            result["error"] = str(e)
        finally:
            await browser.close()

    return result


async def _get_meta(page, selector: str) -> str | None:
    el = await page.query_selector(selector)
    if el:
        return await el.get_attribute("content")
    return None


async def _extract_media_id_from_page(page, shortcode: str | None) -> str | None:
    """Try to find the media ID from page source / scripts."""
    if not shortcode:
        return None

    # Instagram embeds media data in the page HTML
    # Look for "media_id":"XXXXX" or "pk":"XXXXX" near the shortcode
    html = await page.content()

    # Pattern 1: "media_id":"12345"
    patterns = [
        rf'"media_id"\s*:\s*"(\d+)"',
        rf'"pk"\s*:\s*"?(\d+)"?',
    ]

    # Search near the shortcode
    sc_idx = html.find(shortcode)
    if sc_idx > 0:
        # Search in a window around the shortcode
        window = html[max(0, sc_idx - 2000):sc_idx + 2000]
        for pat in patterns:
            match = re.search(pat, window)
            if match:
                return match.group(1)

    # Broader search - look for data-media-id attribute
    attr_match = re.search(r'data-media-id="(\d+)"', html)
    if attr_match:
        return attr_match.group(1)

    # Try the __additionalDataLoaded or similar
    for pat in patterns:
        matches = re.findall(pat, html)
        if matches:
            # Return the most common / first reasonable one
            return matches[0]

    return None


async def _fetch_comments_via_api(context, media_id: str, max_comments: int = 20) -> list[dict]:
    """Fetch comments using Instagram's internal API."""
    comments = []
    page = await context.new_page()

    try:
        api_url = f"https://www.instagram.com/api/v1/media/{media_id}/comments/?can_support_threading=true&permalink_enabled=false"

        response = await page.goto(api_url, wait_until="domcontentloaded", timeout=15000)
        if response and response.ok:
            text = await page.inner_text("pre")
            data = json.loads(text)

            for c in data.get("comments", []):
                user = c.get("user", {}).get("username", "unknown")
                text_val = c.get("text", "")
                if text_val:
                    comments.append({"user": user, "text": text_val})
                if len(comments) >= max_comments:
                    break
    except Exception:
        pass
    finally:
        await page.close()

    return comments
