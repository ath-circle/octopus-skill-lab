"""Apply one reviewed SQL migration through the Supabase Management API."""

import argparse
import asyncio
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


async def apply(migration: Path) -> None:
    load_dotenv()
    project_id = os.getenv("SPB_PROJECT_ID")
    access_token = os.getenv("SPB_ACCESS_TOKEN")
    if not project_id or not access_token:
        raise RuntimeError("SPB_PROJECT_ID and SPB_ACCESS_TOKEN must be set.")
    if not migration.is_file() or migration.suffix != ".sql":
        raise RuntimeError("Provide an existing .sql migration file.")

    payload = {"query": migration.read_text()}
    url = f"https://api.supabase.com/v1/projects/{project_id}/database/query"
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload,
        )
    response.raise_for_status()
    print(f"Applied {migration.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("migration", type=Path)
    args = parser.parse_args()
    asyncio.run(apply(args.migration))


if __name__ == "__main__":
    main()
