"""HTTP transport for guest wallets, server-authoritative rounds and bonuses."""
from datetime import datetime, timezone
from time import time
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import COOKIE_SECURE
from backend.app.core.database import get_db
from backend.app.models import BalanceTransaction, BonusRound, GameRound, Player, SlotGame
from backend.app.schemas import SpinRequest
from backend.app.services.slots import BETS, GAMES, MIN_BET, MAX_BET, play

router = APIRouter(prefix='/api')
DAY = 86_400_000
COOKIE = 'lounge_session'


async def player_for(request: Request, db: AsyncSession, lock: bool = False) -> Player:
    token = request.cookies.get(COOKIE, '')
    statement = select(Player).where(Player.id == token)
    if lock:
        statement = statement.with_for_update()
    player = await db.scalar(statement)
    if player is None:
        raise HTTPException(401, 'Open the lounge to connect your wallet first.')
    return player


async def feature_for(player_id: str, game: str, db: AsyncSession) -> dict | None:
    """Feature progress is persisted in the existing immutable round JSON."""
    record=await db.scalar(select(GameRound).where(
        GameRound.player_id==player_id,GameRound.game==game
    ).order_by(GameRound.created_at.desc(),GameRound.id.desc()).limit(1))
    return record.result.get('feature') if record else None


async def profile(player: Player, db: AsyncSession) -> dict:
    rounds = (await db.scalars(select(BonusRound).where(BonusRound.player_id == player.id))).all()
    saved=[]
    for r in rounds:
        item={'game':r.game,'remaining':r.remaining,'bet':r.bet}
        if r.game=='bigbass' and r.remaining:
            item['feature']=await feature_for(player.id,r.game,db)
        saved.append(item)
    return {'id': player.id, 'balance': player.balance,
            'bonusReadyAt': player.bonus_at + DAY if player.bonus_at else 0,
            'rounds': saved}


def transaction(player: Player, amount: int, kind: str, balance: int, round_id: str | None = None) -> BalanceTransaction:
    return BalanceTransaction(id=str(uuid4()), player_id=player.id, amount=amount,
                              kind=kind, balance_after=balance, round_id=round_id)


@router.get('/games')
async def catalog(db: AsyncSession = Depends(get_db)) -> list[dict]:
    games = (await db.scalars(select(SlotGame))).all()
    return [{'id': g.id, 'name': g.name, 'theme': g.theme, **g.settings,
             'bets': BETS, 'minBet': MIN_BET, 'maxBet': MAX_BET} for g in games]


@router.get('/session')
async def session(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    player = await db.get(Player, request.cookies.get(COOKIE, ''))
    if player is None:
        player = Player(id=str(uuid4()), balance=10000, bonus_at=0)
        db.add(player)
        await db.flush()
        db.add(transaction(player, 10000, 'welcome', 10000))
        await db.commit()
        response.set_cookie(COOKIE, player.id, httponly=True, samesite='strict',
                            secure=COOKIE_SECURE, max_age=31_536_000)
    return await profile(player, db)


@router.post('/spin')
async def spin(payload: SpinRequest, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    async with db.begin():
        # PostgreSQL serializes wallet changes for this player, including other tabs.
        player = await player_for(request, db, lock=True)
        existing = await db.scalar(select(GameRound).where(
            GameRound.player_id == player.id, GameRound.request_id == str(payload.requestId)))
        if existing:
            return existing.result
        bonus = await db.get(BonusRound, (player.id, payload.game))
        remaining = bonus.remaining if bonus else 0
        bet = bonus.bet if remaining else payload.bet
        feature=await feature_for(player.id,payload.game,db) if payload.game=='bigbass' and remaining else None
        try:
            result = play(payload.game, bet, player.balance, remaining,feature=feature)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        result['id'] = str(uuid4())
        result['created_at'] = datetime.now(timezone.utc).isoformat()
        if bonus is None:
            bonus = BonusRound(player_id=player.id, game=payload.game)
            db.add(bonus)
        bonus.bet, bonus.remaining = bet, result['freeSpins']
        db.add(GameRound(id=result['id'], player_id=player.id, game=payload.game,
                         request_id=str(payload.requestId), bet=result['cost'],
                         payout=result['payout'], result=result))
        await db.flush()
        if result['cost']:
            db.add(transaction(player, -result['cost'], 'bet', player.balance-result['cost'], result['id']))
        player.balance = result['balance']
        if result['payout']:
            db.add(transaction(player, result['payout'], 'win', player.balance, result['id']))
    return result


@router.get('/history')
async def history(request: Request, db: AsyncSession = Depends(get_db)) -> list[dict]:
    player = await player_for(request, db)
    records = (await db.scalars(select(GameRound).where(GameRound.player_id == player.id)
                               .order_by(GameRound.created_at.desc()).limit(30))).all()
    return [{'id': r.id, 'game': r.game, 'bet': r.bet, 'payout': r.payout,
             'created_at': r.created_at.isoformat()} for r in records]


@router.get('/rounds/{round_id}')
async def round_result(round_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    player = await player_for(request, db)
    record = await db.get(GameRound, round_id)
    if record is None or record.player_id != player.id:
        raise HTTPException(404, 'Round not found.')
    return record.result


@router.post('/bonus')
async def daily_bonus(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    async with db.begin():
        player = await player_for(request, db, lock=True)
        now = int(time() * 1000)
        if player.bonus_at and now < player.bonus_at + DAY:
            raise HTTPException(409, 'Your next daily gift is on its way.')
        player.balance += 1500
        player.bonus_at = now
        db.add(transaction(player, 1500, 'daily_bonus', player.balance))
    return await profile(player, db)
