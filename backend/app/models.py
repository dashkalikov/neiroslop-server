"""Relational models for the playable visual prototype."""
from datetime import datetime, timezone
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = 'players'
    __table_args__ = (CheckConstraint('balance >= 0'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=10000)
    bonus_at: Mapped[int] = mapped_column(BigInteger, default=0)


class SlotGame(Base):
    __tablename__ = 'slot_games'
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    theme: Mapped[str] = mapped_column(String(50))
    settings: Mapped[dict] = mapped_column(JSON)


class BonusRound(Base):
    __tablename__ = 'bonus_rounds'
    player_id: Mapped[str] = mapped_column(ForeignKey('players.id'), primary_key=True)
    game: Mapped[str] = mapped_column(ForeignKey('slot_games.id'), primary_key=True)
    remaining: Mapped[int] = mapped_column(Integer, default=0)
    bet: Mapped[int] = mapped_column(Integer, default=20)


class GameRound(Base):
    __tablename__ = 'game_rounds'
    __table_args__ = (UniqueConstraint('player_id', 'request_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey('players.id'), index=True)
    game: Mapped[str] = mapped_column(ForeignKey('slot_games.id'))
    request_id: Mapped[str] = mapped_column(String(36))
    bet: Mapped[int] = mapped_column(Integer)
    payout: Mapped[int] = mapped_column(BigInteger)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class BalanceTransaction(Base):
    __tablename__ = 'balance_transactions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey('players.id'), index=True)
    round_id: Mapped[str | None] = mapped_column(ForeignKey('game_rounds.id'), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    amount: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
