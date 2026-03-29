import os


def load_cookies(path: str | None = None) -> list[dict]:
    """Parse a Netscape-format cookies.txt into Playwright cookie dicts."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "cookies.txt")

    cookies = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue

            domain = parts[0]
            # Only keep Instagram cookies
            if "instagram.com" not in domain:
                continue

            try:
                expires = int(parts[4])
            except ValueError:
                expires = -1
            if expires <= 0:
                expires = -1
            elif expires > 10_000_000_000_000:
                # Chrome-style timestamp (microseconds since 1601-01-01)
                # Convert to Unix epoch (seconds since 1970-01-01)
                expires = int((expires / 1_000_000) - 11644473600)
            elif expires > 10_000_000_000:
                # Milliseconds, convert to seconds
                expires = int(expires / 1000)

            cookies.append({
                "name": parts[5],
                "value": parts[6],
                "domain": domain,
                "path": parts[2],
                "secure": parts[3].upper() == "TRUE",
                "expires": expires,
            })

    return cookies
