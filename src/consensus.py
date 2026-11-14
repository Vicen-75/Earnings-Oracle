# --- Javier: V6 component 4, three runs averaged (issue #45; code written with help from Claude) ---
# Each run gives a direction and a probability for that direction. Turned into a probability of an increase, the runs
# are averaged and the call is the side the average favors. Ties go to decrease, the same even-odds rule the V6 prompt
# gives the model ("call decrease whenever a decrease is at least as likely"). Fixed before any V6 run on set B
# (docs/test_plan.md); no threshold is tuned.
#
# The same records give the two free arms of the component ablation: run 1 alone, and a majority vote of directions.


def p_increase(direction, probability):
    if direction == "increase":
        return probability
    if direction == "decrease":
        return 1 - probability
    return None


def _side(p_inc):
    return "increase" if p_inc > 0.5 else "decrease"


def combine(runs):
    """runs: [{"direction", "probability"}, ...] in run order. A run with no direction or no probability is left out
    of the average; if no run is usable the result has no direction (counted wrong, docs/success_metric.md).
    Returns {"direction", "probability", "p_increase_mean", "usable_runs", "run1_direction", "majority_direction"}."""
    usable = [p_increase(r.get("direction"), r["probability"]) for r in runs
              if r.get("direction") in ("increase", "decrease") and isinstance(r.get("probability"), (int, float))]
    usable = [p for p in usable if p is not None]
    votes = [r.get("direction") for r in runs if r.get("direction") in ("increase", "decrease")]
    majority = None
    if votes:
        majority = "increase" if votes.count("increase") > votes.count("decrease") else "decrease"
    first = runs[0].get("direction") if runs else None
    if not usable:
        return {"direction": None, "probability": None, "p_increase_mean": None, "usable_runs": 0,
                "run1_direction": first, "majority_direction": majority}
    mean = sum(usable) / len(usable)
    direction = _side(mean)
    return {"direction": direction, "probability": round(mean if direction == "increase" else 1 - mean, 4),
            "p_increase_mean": round(mean, 4), "usable_runs": len(usable),
            "run1_direction": first, "majority_direction": majority}


if __name__ == "__main__":
    tests = [
        ([{"direction": "increase", "probability": 0.7}] * 3, "increase"),
        ([{"direction": "increase", "probability": 0.55}, {"direction": "decrease", "probability": 0.7},
          {"direction": "increase", "probability": 0.55}], "decrease"),      # mean P(inc) = 0.4667
        ([{"direction": "increase", "probability": 0.6}, {"direction": "decrease", "probability": 0.6},
          {"direction": None, "probability": None}], "decrease"),            # tie at 0.5 goes to decrease
        ([{"direction": None, "probability": None}] * 3, None),
    ]
    for runs, expected in tests:
        got = combine(runs)
        assert got["direction"] == expected, (runs, got)
    r = combine(tests[1][0])
    assert r["majority_direction"] == "increase" and r["run1_direction"] == "increase"
    print("consensus: all checks pass")
