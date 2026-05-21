"""Test the LLM Council with a real game analysis."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.llm_council import get_council


async def test():
    council = get_council()

    game_data = {
        "game_id": "2024_13_KC_LV",
        "home_team": "Las Vegas Raiders",
        "away_team": "Kansas City Chiefs",
        "game_time": "2024-11-29T16:30:00",
        "venue": "Allegiant Stadium",
        "ml_home": 350,
        "ml_away": -450,
        "spread": 9.5,
        "total": 43.5,
        "home_stats": {"record": "2-9", "ppg": 17.2, "papg": 26.1},
        "away_stats": {"record": "10-1", "ppg": 26.5, "papg": 17.9},
    }

    print("Analyzing: Chiefs @ Raiders...")
    print("(This will take ~30 seconds as 4 LLMs analyze in parallel)")

    decision = await council.analyze_game(game_data)

    print("\n" + "=" * 50)
    print("COUNCIL DECISION")
    print("=" * 50)
    print(f"Pick: {decision.pick.upper()}")
    print(f"Tier: {decision.tier}")
    print(f"Confidence: {decision.confidence:.1%}")
    print(f"Consensus: {decision.consensus_pct:.1%}")
    print(f"Edge: {decision.edge:.1%}")
    print(f"\nReasoning: {decision.reasoning[:200]}...")

    if decision.dissenting_views:
        print("\nDissenting views:")
        for view in decision.dissenting_views[:2]:
            print(f"  - {view[:100]}")

    print(f"\nChairman Summary: {decision.chairman_summary[:300]}")

    await council.close()


if __name__ == "__main__":
    asyncio.run(test())

