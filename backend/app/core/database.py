"""One SQLAlchemy session per request, with routes owning transactions."""
from collections.abc import AsyncIterator
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessions() as session:
        yield session
