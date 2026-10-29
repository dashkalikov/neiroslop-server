"""FastAPI application factory; React is served independently by Vite."""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.app.api.routes import router
from backend.app.core.config import ALLOWED_ORIGINS, database_url as configured_url
from backend.app.models import Base, SlotGame
from backend.app.services.slots import GAMES


def create_app(database_url: str | None = None) -> FastAPI:
    engine = create_async_engine(database_url or configured_url(), pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            for id, game in GAMES.items():
                existing = await db.get(SlotGame, id)
                if existing is None:
                    db.add(SlotGame(id=id, name=game['name'], theme=game['theme'], settings=game))
                else:
                    existing.name, existing.theme, existing.settings = game['name'], game['theme'], game
        yield
        await engine.dispose()

    app = FastAPI(title='Lucky Lounge API', version='2.0.0', lifespan=lifespan,
                  description='Server-authoritative virtual-coin games backed by PostgreSQL.')
    app.state.sessions = sessions
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True,
                       allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])
    app.include_router(router)

    @app.middleware('http')
    async def request_boundary(request: Request, call_next):
        if request.method == 'POST' and request.headers.get('origin') not in (None, *ALLOWED_ORIGINS):
            return JSONResponse({'error': 'Origin not allowed.'}, status_code=403)
        try:
            if int(request.headers.get('content-length', '0')) > 16_384:
                return JSONResponse({'error': 'Request too large.'}, status_code=413)
        except ValueError:
            return JSONResponse({'error': 'Invalid request length.'}, status_code=400)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return JSONResponse({'error': error.detail}, status_code=error.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        return JSONResponse({'error': 'Choose a valid game, integer bet, and request ID.'}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error: Exception):
        logging.getLogger(__name__).error('API request failed', exc_info=error)
        return JSONResponse({'error': 'The lounge could not complete that request. Please reconnect.'}, status_code=500)

    @app.get('/api/health')
    async def health():
        async with engine.connect() as connection:
            await connection.execute(text('SELECT 1'))
        return {'status': 'ok', 'server': 'FastAPI', 'database': engine.dialect.name}

    return app


app = create_app()
