from datetime import datetime, timedelta, timezone

from scripts.parlay_generator import ParlayGenerator

NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


def leg(
    leg_id: str,
    event_id: str,
    selection: str,
    *,
    book: str = "ExampleBook",
    odds: int = 150,
    source_hash_char: str = "a",
    estimate_hash_char: str = "b",
):
    return {
        "selection_id": leg_id,
        "team": selection,
        "bet_type": "moneyline",
        "market_snapshot": {
            "snapshot_id": f"snapshot-{leg_id}",
            "event_id": event_id,
            "market_key": "h2h",
            "selection_key": selection,
            "sportsbook": book,
            "source": "archived-api-response",
            "american_odds": odds,
            "observed_at": (NOW - timedelta(seconds=30)).isoformat(),
            "event_start_at": (NOW + timedelta(hours=2)).isoformat(),
            "source_hash": source_hash_char * 64,
        },
        "model_estimate": {
            "estimate_id": f"estimate-{leg_id}",
            "model_id": "model@abc123",
            "evaluation_id": "walk-forward-2026",
            "point_probability": 0.50,
            "lower_probability_bound": 0.45,
            "evidence_status": "out_of_sample_validated",
            "generated_at": (NOW - timedelta(minutes=5)).isoformat(),
            "data_cutoff_at": (NOW - timedelta(hours=1)).isoformat(),
            "artifact_hash": estimate_hash_char * 64,
        },
    }


def payload_with_two_legs(*, mixed_books: bool = False, include_joint: bool = True):
    first = leg("leg-a", "event-a", "Team A", source_hash_char="a")
    second = leg(
        "leg-b",
        "event-b",
        "Team B",
        book="OtherBook" if mixed_books else "ExampleBook",
        source_hash_char="c",
        estimate_hash_char="d",
    )
    payload = {
        "analyses": [
            {
                "game_info": {
                    "game_id": "event-a",
                    "away_team": "Away A",
                    "home_team": "Team A",
                },
                "recommendations": [first],
            },
            {
                "game_info": {
                    "game_id": "event-b",
                    "away_team": "Away B",
                    "home_team": "Team B",
                },
                "recommendations": [second],
            },
        ],
        "joint_estimates": [],
    }
    if include_joint:
        payload["joint_estimates"].append(
            {
                "leg_ids": ["leg-a", "leg-b"],
                "market_snapshot": {
                    "snapshot_id": "parlay-offer-1",
                    "event_id": "event-a+event-b",
                    "market_key": "parlay",
                    "selection_key": "leg-a+leg-b",
                    "sportsbook": "ExampleBook",
                    "source": "archived-parlay-offer",
                    "american_odds": 525,
                    "observed_at": (NOW - timedelta(seconds=20)).isoformat(),
                    "event_start_at": (NOW + timedelta(hours=2)).isoformat(),
                    "source_hash": "e" * 64,
                },
                "model_estimate": {
                    "estimate_id": "joint-estimate-1",
                    "model_id": "joint-model@def456",
                    "evaluation_id": "joint-walk-forward-2026",
                    "point_probability": 0.25,
                    "lower_probability_bound": 0.20,
                    "evidence_status": "out_of_sample_validated",
                    "generated_at": (NOW - timedelta(minutes=4)).isoformat(),
                    "data_cutoff_at": (NOW - timedelta(hours=1)).isoformat(),
                    "artifact_hash": "f" * 64,
                },
            }
        )
    return payload


def test_exact_joint_estimate_and_same_book_offer_can_be_paper_tracked():
    result = ParlayGenerator(now=NOW).generate_all_parlays(payload_with_two_legs())

    assert result["summary"]["paper_track_parlays"] == 1
    assert result["summary"]["live_wagers_authorized"] is False
    candidate = result["2_leg"][0]
    assert candidate["decision"]["status"] == "PAPER_TRACK"
    assert candidate["sportsbook"] == "ExampleBook"
    assert candidate["offered_american_odds"] == 525
    assert candidate["joint_probability_lower_bound"] == 0.20
    assert "warning" in candidate["diagnostic"]


def test_missing_joint_probability_is_blocked_not_multiplied_into_recommendation():
    result = ParlayGenerator(now=NOW).generate_all_parlays(
        payload_with_two_legs(include_joint=False)
    )

    assert result["2_leg"] == []
    assert result["summary"]["paper_track_parlays"] == 0
    assert (
        "missing_pre_registered_joint_probability_and_exact_parlay_offer"
        in result["blocked_candidates"][0]["blockers"]
    )
    assert (
        result["blocked_candidates"][0]["diagnostic"]["point_marginal_product"] == 0.25
    )


def test_mixed_best_prices_from_different_books_are_not_placeable():
    result = ParlayGenerator(now=NOW).generate_all_parlays(
        payload_with_two_legs(mixed_books=True)
    )

    assert result["2_leg"] == []
    assert (
        "legs_do_not_share_one_placeable_sportsbook"
        in result["blocked_candidates"][0]["blockers"]
    )


def test_legacy_missing_odds_are_invalid_and_never_synthesized():
    payload = [
        {
            "game_info": {
                "game_id": "legacy-game",
                "home_team": "Legacy Home",
                "away_team": "Legacy Away",
            },
            "recommendations": [
                {
                    "team": "Legacy Home",
                    "bet_type": "moneyline",
                    "odds": None,
                    "sportsbook": "N/A",
                    "win_probability": 0.65,
                    "confidence_tier": "S",
                }
            ],
        }
    ]

    result = ParlayGenerator(now=NOW).generate_all_parlays(payload)

    assert result["2_leg"] == []
    assert result["summary"]["valid_individual_legs"] == 0
    assert result["summary"]["invalid_individual_legs"] == 1
    blockers = result["invalid_legs"][0]["blockers"]
    assert any("missing required field" in blocker for blocker in blockers)


def test_candidate_space_is_bounded_before_selection_bias_expands():
    recommendations = []
    for index in range(6):
        recommendations.append(
            leg(
                f"leg-{index}",
                f"event-{index}",
                f"Team {index}",
                source_hash_char=hex(index + 1)[2:],
                estimate_hash_char=hex(index + 7)[2:],
            )
        )
    payload = {
        "analyses": [
            {
                "game_info": {"game_id": "placeholder"},
                "recommendations": recommendations,
            }
        ],
        "joint_estimates": [],
    }

    result = ParlayGenerator(now=NOW, max_combinations=10).generate_all_parlays(payload)

    assert result["2_leg"] == []
    assert (
        "candidate_space_exceeds_bound"
        in result["blocked_candidates"][0]["blockers"][0]
    )
