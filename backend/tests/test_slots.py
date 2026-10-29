"""Small migration regression checks, not the sample's testing workstream."""
import pytest
from backend.app.services.slots import evaluate, play


def grid_with_middle(symbols):
    return [["unused-top", s, "unused-bottom"] for s in symbols]


def test_wild_substitution_and_best_valid_payout():
    assert evaluate(grid_with_middle(["gem", "wild", "gem", "orb", "star"]), 20)["payout"] == 40
    assert evaluate(grid_with_middle(["wild"] * 4 + ["gem"]), 20)["payout"] == 500
    assert evaluate(grid_with_middle(["wild"] * 3 + ["scatter", "gem"]), 20)["payout"] == 200


def test_free_rounds_and_neon_multiplier():
    grid = grid_with_middle(["gem", "gem", "gem", "orb", "star"])
    result = play("neon", 20, 5, free_spins=2, grid=grid)
    assert result["cost"] == 0
    assert result["payout"] == 80
    assert result["balance"] == 85
    assert result["freeSpins"] == 1


@pytest.mark.parametrize("game,expected", [("moon", 8), ("temple", 10), ("neon", 6)])
def test_each_theme_awards_its_free_spins(game, expected):
    grid = grid_with_middle(["gem", "orb", "star", "crown", "leaf"])
    grid[0][0] = grid[2][2] = grid[4][0] = "scatter"
    result = play(game, 20, 100, grid=grid)
    assert result["freeSpins"] == expected
    assert result["balance"] == 80


def test_invalid_inputs_and_insufficient_coins():
    for bet in (0, -20, 20.5, True, 123456):
        with pytest.raises(ValueError, match="bet"):
            play("moon", bet, 100)
    with pytest.raises(ValueError, match="coins"):
        play("moon", 100, 20)
    with pytest.raises(ValueError, match="game"):
        play("unknown", 20, 100)


def test_custom_integer_wagers_and_new_game_layouts():
    grid = grid_with_middle(['gem', 'star', 'leaf', 'crown', 'orb'])
    result = play('moon', 37, 100, grid=grid)
    assert result['cost'] == 37
    assert result['balance'] == 63
    classic = play('royal', 37, 100)
    assert len(classic['grid']) == 3
    assert len(classic['grid'][0]) == 3
    assert len(play('ocean', 37, 100)['grid']) == 5


def test_classic_three_reel_combinations_and_ocean_bonus():
    classic = play('royal', 10, 100, grid=grid_with_middle(['gem','wild','gem']))
    assert classic['payout'] == 20
    assert classic['lines'][0]['cells'] == [[0,1],[1,1],[2,1]]
    ocean = play('ocean', 10, 5, free_spins=1, grid=grid_with_middle(['gem','gem','gem','leaf','orb']))
    assert ocean['payout'] == 60
    assert ocean['balance'] == 65


def test_goldrush_collects_a_cascade_without_charging_another_wager(monkeypatch):
    from backend.app.services import slots
    # Only the middle line wins. Its replacement must drop in above the survivors.
    grid = [['star', 'gem', 'orb'], ['leaf', 'gem', 'crown'],
            ['orb', 'gem', 'leaf'], ['crown', 'star', 'orb'], ['leaf', 'orb', 'star']]
    before = [reel[:] for reel in grid]
    replacements = iter(['crown', 'orb', 'star'])
    monkeypatch.setattr(slots, 'choice', lambda _: next(replacements))
    result = slots.play('goldrush', 20, 100, grid=grid)
    assert result['cost'] == 20
    assert result['payout'] == 40
    assert result['balance'] == 120
    assert result['cascadeCount'] == 1
    assert result['cascades'][1]['grid'][0] == ['crown', 'star', 'orb']
    assert result['cascades'][1]['payout'] == 0
    assert grid == before  # Saved initial results must not be mutated by refills.


def test_goldrush_caps_cascades_and_credits_all_awards_once(monkeypatch):
    from backend.app.services import slots
    monkeypatch.setattr(slots, 'choice', lambda _: 'gem')
    result = slots.play('goldrush', 10, 5, free_spins=1, grid=[['gem'] * 3 for _ in range(5)])
    assert result['cost'] == 0
    assert result['cascadeCount'] == 8
    assert result['payout'] == 8000  # 5 lines x 20 x bet 10 x 8 cascades.
    assert result['balance'] == 8005
    assert result['freeSpins'] == 0


def test_goldrush_bonus_is_awarded_once_per_round():
    grid = grid_with_middle(['gem','star','orb','crown','leaf'])
    grid[0][0] = grid[2][2] = grid[4][0] = 'scatter'
    result = play('goldrush', 37, 100, grid=grid)
    assert result['bonusTriggered'] is True
    assert result['freeSpins'] == 10
    assert result['balance'] == 63
