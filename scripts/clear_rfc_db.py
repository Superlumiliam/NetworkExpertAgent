import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tools.rfc_tools import clear_rfc_knowledge_base


async def run() -> int:
    await clear_rfc_knowledge_base()
    print("RFC knowledge base cleared.")
    return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except Exception as exc:
        print(f"Failed to clear RFC knowledge base: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
