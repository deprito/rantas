#!/usr/bin/env python3
"""Load typosquat regex patterns into HuntingConfig.

This script loads the clean typosquat patterns from
typosquat_patterns_clean.py into the database HuntingConfig.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import get_db_context
from app.models import HuntingConfig as HuntingConfigModel
from sqlalchemy import select


# Import the clean patterns
def get_typosquat_patterns() -> dict:
    """Get typosquat patterns from the clean patterns file."""
    return {
        "example": [
            # Leetspeak core (0=o, 1=i/l, 4=a, 3=e, etc.)
            r"[3e][1x]4mpl[3e]",
            r"[3e]x[4a]mpl[3e]",
            r"[3e]x[4a]mp1[3e]",
            r"[3e]xx[4a]mpl[3e]",
            r"[3e]x[4a]mm[4a]pl[3e]",
            r"[3e]x[4a]mpl[3e][3e]",

            # Suspicious TLD combinations
            r"[3e]x[4a]mpl[3e].*\.(cc|xyz|top|club|icu|tk|ml|click|cloud|online|site)",
            r"[3e]x[4a]mp1[3e].*\.(cc|xyz|top|club|icu|tk|ml|click|cloud|online|site)",

            # Missing/extra letters
            r"[3e]x[4a]mpl[.]?",
            r"[3e]x[4a]mpel",
            r"[3e]xamp1[3e]",

            # Combined with suspicious keywords
            r"[3e]x[4a]mpl[3e].*(login|secure|verify|account|update)",
            r"(login|secure|verify|account|update).*[3e]x[4a]mpl[3e]",
        ],
        "testcorp": [
            # Leetspeak substitutions
            r"[7t][3e][5s][7t]c[0o]rp",
            r"[7t][3e]s[7t]c[0o]rp",
            r"[7t][3e][5s][7t]c[o0]r[p9]",
            r"[7t][3e]s[7t]c[o0][r][p9]",

            # Double letters (obvious typos)
            r"[7t][3e]ss[7t]c[o0]rp",
            r"[7t][3e]s[7t][7t]c[o0]rp",
            r"[7t][3e]s[7t]cc[o0]rp",
            r"[7t][3e]s[7t]c[o0]rrp",
            r"[7t][3e]s[7t]c[o0]rpp",

            # Suspicious TLD combinations
            r"[7t][3e]s[7t]c[o0]rp.*\.(cc|xyz|top|club|icu|tk|ml|click|cloud|online|site)",

            # Combined with suspicious keywords
            r"[7t][3e]s[7t]c[o0]rp.*(login|secure|verify|account)",
            r"(login|secure|verify|account).*[7t][3e]s[7t]c[o0]rp",
        ],
    }


async def load_patterns():
    """Load typosquat patterns into HuntingConfig."""
    patterns = get_typosquat_patterns()

    print("=" * 60)
    print("Loading Typosquat Patterns into HuntingConfig")
    print("=" * 60)

    async with get_db_context() as db:
        # Get existing config
        result = await db.execute(select(HuntingConfigModel))
        config = result.scalar_one_or_none()

        if config:
            print(f"\nUpdating existing config...")
            old_patterns = config.custom_brand_regex_patterns or {}
            config.custom_brand_regex_patterns = patterns
            print(f"  Old patterns: {list(old_patterns.keys())}")
            print(f"  New patterns: {list(patterns.keys())}")
        else:
            print(f"\nCreating new config...")
            config = HuntingConfigModel(
                monitor_enabled=True,
                min_score_threshold=50,
                alert_threshold=80,
                monitored_brands=list(patterns.keys()),
                retention_days=90,
                raw_log_retention_days=3,
                custom_brand_regex_patterns=patterns,
            )
            db.add(config)

        await db.commit()
        await db.refresh(config)

        print(f"\nPatterns loaded successfully!")
        print(f"  Monitored brands: {config.monitored_brands}")
        print(f"  Regex patterns: {list(config.custom_brand_regex_patterns.keys())}")

        for brand, brand_patterns in config.custom_brand_regex_patterns.items():
            print(f"    {brand}: {len(brand_patterns)} patterns")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(load_patterns())
