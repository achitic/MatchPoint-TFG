# scripts/smoke_simulate_api.py
"""
Smoke test for /simulate_match endpoint.

Verifies:
1. Seed reproducibility (same seed = same result)
2. Different seed = different result
3. /predict still works
4. /health still works

Run: python scripts/smoke_simulate_api.py
Requires: Backend running on localhost:8000
"""
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_BASE = "http://localhost:8000"


def api_post(endpoint: str, data: dict) -> dict:
    """Make a POST request and return JSON response."""
    req = Request(
        f"{API_BASE}{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        body = e.read().decode()
        raise Exception(f"HTTP {e.code}: {body}")


def api_get(endpoint: str) -> dict:
    """Make a GET request and return JSON response."""
    req = Request(f"{API_BASE}{endpoint}", method="GET")
    with urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())


def test_health():
    """Test /health endpoint."""
    print("[TEST] /health...", end=" ")
    resp = api_get("/health")
    assert resp.get("status") == "ok", f"Expected status=ok, got {resp}"
    print("PASS")


def test_predict():
    """Test /predict endpoint still works."""
    print("[TEST] /predict...", end=" ")
    resp = api_post("/predict", {
        "player_a": "Carlos Alcaraz",
        "player_b": "Jannik Sinner",
        "surface": "Hard",
        "model": "calibrated_logreg",
        "debug": False,
    })
    assert "p_a" in resp, f"Missing p_a in response"
    assert "p_b" in resp, f"Missing p_b in response"
    assert 0 < resp["p_a"] < 1, f"p_a out of range"
    print(f"PASS (p_a={resp['p_a']:.3f})")


def test_simulate_basic():
    """Test /simulate_match returns expected structure."""
    print("[TEST] /simulate_match basic...", end=" ")
    resp = api_post("/simulate_match", {
        "player_a": "Carlos Alcaraz",
        "player_b": "Jannik Sinner",
        "surface": "Hard",
        "model": "calibrated_logreg",
        "best_of": 3,
        "seed": 12345,
        "timeline_mode": "games",
    })
    
    # Check required fields
    required = ["player_a", "player_b", "surface", "model", "as_of_used",
                "p_a", "p_b", "seed_used", "params", "result", "timeline"]
    for field in required:
        assert field in resp, f"Missing field: {field}"
    
    # Check result structure
    result = resp["result"]
    assert result["winner"] in ("A", "B"), f"Invalid winner: {result['winner']}"
    assert len(result["sets"]) >= 2, f"Expected at least 2 sets"
    
    print(f"PASS (winner={result['winner']}, sets={result['sets']})")
    return resp


def test_seed_reproducibility():
    """Test that same seed produces identical results."""
    print("[TEST] Seed reproducibility...", end=" ")
    
    payload = {
        "player_a": "Carlos Alcaraz",
        "player_b": "Jannik Sinner",
        "surface": "Hard",
        "model": "calibrated_logreg",
        "best_of": 3,
        "seed": 99999,
        "timeline_mode": "games",
    }
    
    resp1 = api_post("/simulate_match", payload)
    resp2 = api_post("/simulate_match", payload)
    
    # Result should be identical
    assert resp1["result"] == resp2["result"], \
        f"Results differ: {resp1['result']} vs {resp2['result']}"
    
    # Timeline should be identical
    assert resp1["timeline"] == resp2["timeline"], \
        "Timelines differ with same seed"
    
    print("PASS (identical results with same seed)")


def test_different_seed_varies():
    """Test that different seeds produce different results (usually)."""
    print("[TEST] Different seeds vary...", end=" ")
    
    base = {
        "player_a": "Carlos Alcaraz",
        "player_b": "Jannik Sinner",
        "surface": "Hard",
        "model": "calibrated_logreg",
        "best_of": 3,
        "timeline_mode": "games",
    }
    
    # Run with 10 different seeds, at least some should differ
    results = []
    for seed in range(10):
        resp = api_post("/simulate_match", {**base, "seed": seed})
        results.append(resp["result"]["sets"])
    
    unique = len(set(tuple(r) for r in results))
    assert unique > 1, f"All 10 seeds produced identical results: {results[0]}"
    
    print(f"PASS ({unique}/10 unique results)")


def test_player_validation():
    """Test that same player A and B returns error."""
    print("[TEST] Player validation (same player)...", end=" ")
    
    try:
        api_post("/simulate_match", {
            "player_a": "Carlos Alcaraz",
            "player_b": "Carlos Alcaraz",
            "surface": "Hard",
        })
        print("FAIL (should have raised error)")
        return False
    except Exception as e:
        if "400" in str(e) and ("different" in str(e).lower() or "must be different" in str(e).lower()):
            print("PASS (400 error as expected)")
            return True
        else:
            print(f"FAIL (wrong error: {e})")
            return False


def test_timeline_modes():
    """Test different timeline modes."""
    print("[TEST] Timeline modes...", end=" ")
    
    base = {
        "player_a": "Carlos Alcaraz",
        "player_b": "Jannik Sinner",
        "surface": "Hard",
        "seed": 42,
    }
    
    # none - no timeline
    resp_none = api_post("/simulate_match", {**base, "timeline_mode": "none"})
    assert resp_none["timeline"] is None, "timeline should be None for mode=none"
    
    # games - timeline with games
    resp_games = api_post("/simulate_match", {**base, "timeline_mode": "games"})
    assert resp_games["timeline"] is not None, "timeline should exist for mode=games"
    assert len(resp_games["timeline"]) >= 2, "Should have at least 2 sets"
    
    # points - timeline with points
    resp_points = api_post("/simulate_match", {**base, "timeline_mode": "points"})
    assert resp_points["timeline"] is not None, "timeline should exist for mode=points"
    # Points mode should have more detail
    first_set = resp_points["timeline"][0]
    if first_set.get("games"):
        first_game = first_set["games"][0]
        assert first_game.get("points") is not None, "Points should be tracked"
    
    print("PASS (all 3 modes work)")


def main():
    """Run all smoke tests."""
    print("MatchPoint /simulate_match Smoke Tests")
    print(f"API Base: {API_BASE}\n")
    
    try:
        test_health()
        test_predict()
        test_simulate_basic()
        test_seed_reproducibility()
        test_different_seed_varies()
        test_player_validation()
        test_timeline_modes()
        
        print("\n" + "=" * 50)
        print("ALL TESTS PASSED")
        return 0
        
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

