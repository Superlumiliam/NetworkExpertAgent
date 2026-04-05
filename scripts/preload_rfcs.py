import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.rfc_catalog import SUPPORTED_RFC_IDS
from src.tools.rfc_tools import preload_rfc_documents


async def run() -> int:
    print("Preloading RFCs:", ", ".join(SUPPORTED_RFC_IDS))
    results = await preload_rfc_documents(SUPPORTED_RFC_IDS)
    for result in results:
        print(f"RFC {result['rfc_id']}: indexed {result['chunks']} chunks")
    print("RFC preload completed.")
    return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except Exception as exc:
        print(f"RFC preload failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
