"""Saloon Luck integrates with the authoritative wallet and bonus rules."""
from backend.app.services.slots import play


def test_saloon_three_reel_wild_win_and_double_bonus():
    grid = [['orb','gem','leaf'],['leaf','wild','star'],['star','gem','crown']]
    paid = play('saloon', 37, 100, grid=grid)
    assert paid['cost'] == 37
    assert paid['payout'] == 74
    assert paid['balance'] == 137
    bonus = play('saloon', 37, 0, free_spins=2, grid=grid)
    assert bonus['cost'] == 0
    assert bonus['multiplier'] == 2
    assert bonus['payout'] == 148
    assert bonus['balance'] == 148
    assert bonus['freeSpins'] == 1


def test_crystal_bonus_awards_eight_spins_and_generated_grid_is_three_by_three():
    grid = [['scatter','orb','leaf'],['gem','scatter','star'],['leaf','crown','scatter']]
    result = play('saloon', 10, 100, grid=grid)
    assert result['bonusTriggered'] is True
    assert result['freeSpins'] == 8
    assert result['balance'] == 90
    generated = play('saloon', 10, 100)
    assert len(generated['grid']) == 3
    assert all(len(reel) == 3 for reel in generated['grid'])

