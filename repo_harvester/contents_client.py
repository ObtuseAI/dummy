import os
import httpx
import base64

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

async def fetch_repo_tree(owner: str, name: str, sha: str = "HEAD"):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.github.com/repos/{owner}/{name}/git/trees/{sha}?recursive=1", headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()

async def fetch_file(owner: str, name: str, path: str, ref: str = "HEAD"):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.github.com/repos/{owner}/{name}/contents/{path}?ref={ref}", headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("content"):
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return ""
