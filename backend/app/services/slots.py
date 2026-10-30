"""Pure game rules; independent from HTTP and database storage."""

from secrets import choice

GAMES = {
    "saloon": {"name": "Saloon Luck", "bonus": 8, "multiplier": 2, "theme": "Mechanical", "reels": 3},
    "moon": {"name": "Moonlight Magic", "bonus": 8, "multiplier": 1, "theme": "Fantasy", "reels": 5},
    "temple": {"name": "Temple of Gold", "bonus": 10, "multiplier": 1, "theme": "Adventure", "reels": 5},
    "neon": {"name": "Neon Nights", "bonus": 6, "multiplier": 2, "theme": "Neon", "reels": 5},
    "royal": {"name": "Velvet Sevens", "bonus": 7, "multiplier": 1, "theme": "Classic", "reels": 3},
    "ocean": {"name": "Ocean Myth", "bonus": 7, "multiplier": 3, "theme": "Ocean", "reels": 5},
    "goldrush": {"name": "Goldrush Canyon", "bonus": 10, "multiplier": 1, "theme": "Adventure", "reels": 5, "cascading": True},
    "bigbass": {"name": "Big Bass Bonanza", "bonus": 10, "multiplier": 1, "theme": "Fishing", "reels": 5, "paylines": 10},
}
BETS = (10, 20, 50, 100, 200, 500)
MIN_BET, MAX_BET = 1, 10000
PAYLINES = ((1, 1, 1, 1, 1), (0, 0, 0, 0, 0), (2, 2, 2, 2, 2), (0, 1, 2, 1, 0), (2, 1, 0, 1, 2))
CLASSIC_PAYLINES = ((1,1,1), (0,0,0), (2,2,2), (0,1,0), (2,1,2))
SYMBOLS = ("gem", "star", "orb", "crown", "leaf", "wild")
BAG = ("gem", "gem", "gem", "star", "star", "star", "orb", "orb", "orb", "crown", "crown", "leaf", "leaf", "leaf", "wild", "scatter")


def evaluate(grid: list[list[str]], bet: int) -> dict:
    """Award the best eligible match on each left-to-right payline."""
    lines = []
    for index, rows in enumerate(CLASSIC_PAYLINES if len(grid) == 3 else PAYLINES):
        symbols = [grid[column][row] for column, row in enumerate(rows)]
        best = None
        for symbol in SYMBOLS:
            count = 0
            for current in symbols:
                if current not in (symbol, "wild"):
                    break
                count += 1
            if count >= 3:
                table = (0, 0, 0, 10, 25, 100) if symbol == "wild" else (0, 0, 0, 2, 5, 20)
                payout = bet * table[count]
                if best is None or payout > best["payout"]:
                    best = {"index": index, "symbol": symbol, "count": count, "payout": payout,
                            "cells": [[c, rows[c]] for c in range(count)]}
        if best:
            lines.append(best)
    return {"payout": sum(line["payout"] for line in lines), "lines": lines,
            "scatters": sum(symbol == "scatter" for reel in grid for symbol in reel)}


def play(game: str, bet: int, balance: int, free_spins: int = 0, grid: list[list[str]] | None = None, feature: dict | None = None) -> dict:
    """Calculate a round using server-generated cryptographic randomness."""
    if game not in GAMES:
        raise ValueError("Unknown game.")
    if type(bet) is not int or not MIN_BET <= bet <= MAX_BET:
        raise ValueError("Choose a whole-coin bet from 1 to 10,000.")
    cost = 0 if free_spins > 0 else bet
    if balance < cost:
        raise ValueError("Not enough coins. Lower your bet or claim your daily gift.")
    if game == 'bigbass':
        from .big_bass import play as play_big_bass
        return play_big_bass(bet,balance,free_spins,grid,feature)
    grid = grid if grid is not None else [[choice(BAG) for _ in range(3)] for _ in range(GAMES[game]['reels'])]
    result = evaluate(grid, bet)
    cascade_data = {}
    if GAMES[game].get('cascading'):
        frames = []
        current = [reel[:] for reel in grid]
        # A single wager funds the full sequence. Bound work and total awards.
        for _ in range(8):
            frame = evaluate(current, bet)
            frames.append({**frame, 'grid': current})
            if not frame['payout']:
                break
            removed = {tuple(cell) for line in frame['lines'] for cell in line['cells']}
            current = [
                [choice(BAG) for _ in range(sum((c, r) in removed for r in range(3)))]
                + [symbol for r, symbol in enumerate(reel) if (c, r) not in removed]
                for c, reel in enumerate(current)
            ]
        result = {**result, 'payout': sum(f['payout'] for f in frames),
                  'scatters': max(f['scatters'] for f in frames)}
        cascade_data = {'cascades': frames, 'cascadeCount': sum(f['payout'] > 0 for f in frames)}
    multiplier = GAMES[game]["multiplier"] if free_spins else 1
    payout = result["payout"] * multiplier
    triggered = result["scatters"] >= 3
    return {**result, **cascade_data, "grid": grid, "game": game, "bet": bet, "cost": cost,
            "payout": payout, "multiplier": multiplier, "bonusTriggered": triggered,
            "balance": balance - cost + payout,
            "freeSpins": max(0, free_spins - 1) + (GAMES[game]["bonus"] if triggered else 0)}
