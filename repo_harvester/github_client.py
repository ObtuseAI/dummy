import os
import httpx

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

async def fetch_repo_metadata(owner: str, name: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.github.com/repos/{owner}/{name}", headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()

async def fetch_languages(owner: str, name: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.github.com/repos/{owner}/{name}/languages", headers=HEADERS, timeout=20)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()
