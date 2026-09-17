"""Read-only setup checker. It never prints secret values."""

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv


async def check() -> int:
    load_dotenv()
    project_id = os.getenv("SPB_PROJECT_ID")
    secret_key = os.getenv("SPB_SECRET_KEY")
    if not project_id or not secret_key:
        print("FAIL  SPB_PROJECT_ID and SPB_SECRET_KEY must be set.")
        return 1

    base_url = f"https://{project_id}.supabase.co"
    headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}
    checks = [
        ("Supabase REST", f"{base_url}/rest/v1/", None),
        ("Registry table", f"{base_url}/rest/v1/skills?select=id&limit=1", None),
        ("Job table", f"{base_url}/rest/v1/jobs?select=id&limit=1", None),
        ("Artifact bucket", f"{base_url}/storage/v1/bucket/skill-artifacts", None),
    ]
    failed = False
    async with httpx.AsyncClient(timeout=15) as client:
        for label, url, params in checks:
            try:
                response = await client.get(url, headers=headers, params=params)
                if response.is_success:
                    print(f"OK    {label}")
                else:
                    print(f"FAIL  {label} (HTTP {response.status_code})")
                    failed = True
            except httpx.HTTPError:
                print(f"FAIL  {label} (unreachable)")
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(check()))
