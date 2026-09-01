"""
Obligation Agent — Seed Script.
Delegates to app.ops.seed_demo for consistent, rich demo environment initialization.
"""

import sys
import asyncio
from app.ops.seed_demo import seed_demo_environment

if __name__ == "__main__":
    force = "--force-production" in sys.argv
    asyncio.run(seed_demo_environment(force_production=force))
