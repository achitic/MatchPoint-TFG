#!/usr/bin/env python3
"""
Smoke test for tournament API endpoints.

Verifies:
1. GET /models returns catalog with Spanish labels
2. GET /tournaments returns real tournament list
3. POST /tournament/simulate works with seed reproducibility
4. Regression: existing endpoints still work

Usage:
    # Start server first
    uvicorn backend.main:app --reload
    
    # Run tests
    python scripts/smoke_tournament_api.py
"""
import httpx
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000"


def test_models_catalog():
    """Test GET /models returns catalog with Spanish labels."""
    print("\n[1] Testing GET /models...")
    
    resp = httpx.get(f"{BASE}/models")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    data = resp.json()
    assert "models" in data, "Missing 'models' key"
    
    models = data["models"]
    assert len(models) >= 3, f"Expected at least 3 models, got {len(models)}"
    
    # Check structure
    for m in models:
        assert "id" in m, "Missing 'id'"
        assert "label_es" in m, "Missing 'label_es'"
        assert "description_es" in m, "Missing 'description_es'"
    
    # Check specific model
    calibrated = next((m for m in models if m["id"] == "calibrated_logreg"), None)
    assert calibrated is not None, "calibrated_logreg not found"
    assert "calibrado" in calibrated["label_es"].lower(), (
        f"Expected 'calibrado' in label, got {calibrated['label_es']}"
    )
    
    print(f"   Found {len(models)} models with Spanish labels")
    print(f"   Example: {calibrated}")
    return True


def test_tournaments_catalog():
    """Test GET /tournaments returns real tournaments."""
    print("\n[2] Testing GET /tournaments...")
    
    resp = httpx.get(f"{BASE}/tournaments", params={"limit": 10})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    data = resp.json()
    assert "tournaments" in data, "Missing 'tournaments' key"
    assert "count" in data, "Missing 'count' key"
    
    tournaments = data["tournaments"]
    assert len(tournaments) > 0, "No tournaments returned"
    assert len(tournaments) <= 10, f"Expected max 10, got {len(tournaments)}"
    
    # Check structure
    t = tournaments[0]
    assert "id" in t, "Missing 'id'"
    assert "name" in t, "Missing 'name'"
    assert "surface" in t, "Missing 'surface'"
    assert "date" in t, "Missing 'date'"
    assert "level" in t, "Missing 'level'"
    assert "year" in t, "Missing 'year'"
    
    print(f"   Found {data['count']} tournaments (showing first 10)")
    print(f"   First tournament: {t['name']} ({t['surface']}, {t['date']})")
    
    # Test filters
    resp2 = httpx.get(f"{BASE}/tournaments", params={"surface": "Clay", "limit": 5})
    assert resp2.status_code == 200
    clay_tournaments = resp2.json()["tournaments"]
    if clay_tournaments:
        assert all(t["surface"] == "Clay" for t in clay_tournaments), "Surface filter not working"
        print(f"   Surface filter works ({len(clay_tournaments)} Clay tournaments)")
    
    return True


def test_tournament_simulation():
    """Test POST /tournament/simulate with reproducibility."""
    print("\n[3] Testing POST /tournament/simulate...")
    
    # Use 8 known players
    players = [
        "Novak Djokovic",
        "Carlos Alcaraz",
        "Jannik Sinner", 
        "Daniil Medvedev",
        "Alexander Zverev",
        "Stefanos Tsitsipas",
        "Casper Ruud",
        "Andrey Rublev",
    ]
    
    request = {
        "players": players,
        "size": 8,
        "surface": "Hard",
        "model": "calibrated_logreg",
        "best_of": 3,
        "seed": 42,
        "seeding": "random",
        "timeline_mode": "none",
    }
    
    # First run
    resp1 = httpx.post(f"{BASE}/tournament/simulate", json=request, timeout=60)
    assert resp1.status_code == 200, f"Expected 200, got {resp1.status_code}: {resp1.text[:200]}"
    
    data1 = resp1.json()
    
    # Check response structure
    assert "tournament" in data1, "Missing 'tournament'"
    assert "rounds" in data1, "Missing 'rounds'"
    assert "champion" in data1, "Missing 'champion'"
    assert "standings" in data1, "Missing 'standings'"
    assert "seed_used" in data1, "Missing 'seed_used'"
    
    champion1 = data1["champion"]
    rounds1 = len(data1["rounds"])
    bracket1 = data1["bracket_order"]
    seed_used = data1["seed_used"]
    
    print(f"   Champion: {champion1}")
    print(f"   Rounds: {rounds1}")
    print(f"   Seed used: {seed_used}")
    print(f"   Bracket order: {bracket1[:4]}...")
    
    # Check rounds structure
    assert rounds1 == 3, f"Expected 3 rounds for 8 players, got {rounds1}"
    
    for r in data1["rounds"]:
        assert "round" in r, "Missing round number"
        assert "name" in r, "Missing round name"
        assert "matches" in r, "Missing matches"
        
        for m in r["matches"]:
            assert "player_a" in m, "Missing player_a"
            assert "player_b" in m, "Missing player_b"
            assert "p_a" in m, "Missing p_a"
            assert "result" in m, "Missing result"
            assert "winner_name" in m["result"], "Missing winner_name in result"
    
    # Check standings
    for player in players:
        assert player in data1["standings"], f"Player {player} not in standings"
        stats = data1["standings"][player]
        assert "wins" in stats, "Missing wins"
        assert "losses" in stats, "Missing losses"
    
    # Reproducibility test - same seed
    print("\n   Testing reproducibility (same seed)...")
    resp2 = httpx.post(f"{BASE}/tournament/simulate", json=request, timeout=60)
    assert resp2.status_code == 200
    
    data2 = resp2.json()
    champion2 = data2["champion"]
    bracket2 = data2["bracket_order"]
    
    assert champion1 == champion2, f"Champions differ with same seed: {champion1} vs {champion2}"
    assert bracket1 == bracket2, f"Bracket order differs with same seed"
    
    print(f"   Same seed produces identical result: {champion2}")
    
    # Different seed test
    print("\n   Testing variation (different seed)...")
    request["seed"] = 123
    resp3 = httpx.post(f"{BASE}/tournament/simulate", json=request, timeout=60)
    assert resp3.status_code == 200
    
    data3 = resp3.json()
    bracket3 = data3["bracket_order"]
    
    # Bracket order should be different with different seed (very likely)
    if bracket3 == bracket1:
        print("   Warning: same bracket with different seed (possible but unlikely)")
    else:
        print(f"   Different seed produces different bracket: {bracket3[:4]}...")
    
    return True


def test_tournament_with_timeline():
    """Test tournament simulation with timeline_mode=games."""
    print("\n[4] Testing tournament with timeline...")
    
    players = [
        "Roger Federer", "Rafael Nadal",
        "Novak Djokovic", "Andy Murray",
        "Stan Wawrinka", "Marin Cilic",
        "Juan Martin Del Potro", "Kei Nishikori",
    ]
    
    request = {
        "players": players,
        "size": 8,
        "surface": "Grass",
        "model": "calibrated_logreg",
        "best_of": 3,
        "seed": 999,
        "seeding": "random",
        "timeline_mode": "games",
    }
    
    resp = httpx.post(f"{BASE}/tournament/simulate", json=request, timeout=60)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    data = resp.json()
    
    # Check that timeline is populated
    first_match = data["rounds"][0]["matches"][0]
    assert "timeline" in first_match, "Missing timeline"
    assert first_match["timeline"] is not None, "Timeline should not be None"
    assert len(first_match["timeline"]) > 0, "Timeline should not be empty"
    
    print(f"   Timeline present with {len(first_match['timeline'])} sets")
    print(f"   Champion: {data['champion']}")
    
    return True


def test_regression_predict():
    """Verify /predict still works."""
    print("\n[5] Regression: Testing /predict...")
    
    resp = httpx.post(f"{BASE}/predict", json={
        "player_a": "Novak Djokovic",
        "player_b": "Carlos Alcaraz",
        "surface": "Hard",
        "model": "calibrated_logreg",
    })
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "p_a" in data, "Missing p_a"
    assert 0 <= data["p_a"] <= 1, "p_a out of range"
    
    print(f"   /predict OK: {data['player_a']} vs {data['player_b']} -> p_a={data['p_a']:.3f}")
    return True


def test_regression_simulate_match():
    """Verify /simulate_match still works."""
    print("\n[6] Regression: Testing /simulate_match...")
    
    resp = httpx.post(f"{BASE}/simulate_match", json={
        "player_a": "Roger Federer",
        "player_b": "Rafael Nadal",
        "surface": "Clay",
        "model": "calibrated_logreg",
        "best_of": 3,
        "seed": 42,
    })
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "result" in data, "Missing result"
    assert "seed_used" in data, "Missing seed_used"
    
    print(f"   /simulate_match OK: Winner={data['result']['winner']}, Sets={data['result']['sets']}")
    return True


def test_regression_health():
    """Verify /health still works."""
    print("\n[7] Regression: Testing /health...")
    
    resp = httpx.get(f"{BASE}/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert resp.json()["status"] == "ok"
    
    print("   /health OK")
    return True


def main():
    print("MatchPoint Tournament API Smoke Tests")
    
    tests = [
        ("Models Catalog", test_models_catalog),
        ("Tournaments Catalog", test_tournaments_catalog),
        ("Tournament Simulation", test_tournament_simulation),
        ("Tournament Timeline", test_tournament_with_timeline),
        ("Regression /predict", test_regression_predict),
        ("Regression /simulate_match", test_regression_simulate_match),
        ("Regression /health", test_regression_health),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"\n   FAILED: {e}")
            failed += 1
        except httpx.ConnectError:
            print(f"\n   FAILED: Could not connect to server at {BASE}")
            print("   Make sure the server is running: uvicorn backend.main:app --reload")
            failed += 1
        except Exception as e:
            print(f"\n   FAILED with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

