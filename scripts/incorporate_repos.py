import asyncio
from repo_harvester.runner import run_v2_with_source_scan
from repo_harvester.incorporation_engine import incorporate_adapter_plans


async def main():
    print("Running V2 repo harvester with source scan (limit 20)...")
    await run_v2_with_source_scan(limit=20)
    result = incorporate_adapter_plans(require_tests=True)
    print(f"Incorporated: {len(result['incorporated'])}, rejected: {len(result['rejected'])}")


if __name__ == "__main__":
    asyncio.run(main())
