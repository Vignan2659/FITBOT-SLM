"""FitBot FastAPI application.

Run:  cd backend && ../.venv/bin/uvicorn app.main:app --port 8000
The SLM, retriever and intent classifier are loaded ONCE in the lifespan handler.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, catalog_routes, chat, conversations
from app.core.config import get_settings
from app.db.database import engine
from app.db.seed import init_db
from app.ml.retriever import KnowledgeRetriever
from app.services.catalog import Catalog
from app.services.chat_engine import ChatEngine
from app.services.nlu import NLU

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("fitbot")


def build_engine(settings, generate=None) -> tuple[ChatEngine, dict]:
    data_dir = Path(settings.data_dir)
    catalog = Catalog(data_dir)
    retriever = KnowledgeRetriever(data_dir / "knowledge" / "knowledge_base.json", settings.fitbot_embed_model,
                                   use_embeddings=settings.fitbot_use_embeddings)
    nlu = NLU(Path(settings.models_dir) / "intent_classifier.joblib", catalog.exercises, catalog.foods,
              encode=retriever.encode if retriever.backend != "tfidf" else None)
    info = {"retriever": retriever.backend, "intent_classifier": nlu.clf is not None,
            "intent_embeddings": bool(getattr(nlu.clf, "uses_embeddings", False))}
    if generate is None:
        from app.ml.slm import FitBotSLM
        slm = FitBotSLM(settings.model_ref(), settings.fitbot_base_model,
                        settings.fitbot_device, settings.fitbot_max_new_tokens)
        generate = slm.generate
        info["slm"] = slm.info()
    else:
        info["slm"] = {"model": "injected test generator", "fine_tuned": False}
    return ChatEngine(catalog, nlu, retriever, generate, settings.fitbot_history_turns), info


class StripApiPrefix:
    """ASGI middleware: '/api/...' -> '/...'. The React app calls '/api/*' both behind the Vite dev proxy and
    when FastAPI serves the built frontend itself (single-origin production deployment)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (scope["path"] == "/api" or scope["path"].startswith("/api/")):
            scope = dict(scope)
            scope["path"] = scope["path"][4:] or "/"
            scope["raw_path"] = scope["path"].encode()
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.is_production and settings.jwt_secret in ("change-me-in-backend-.env", "change-me", ""):
        raise RuntimeError("Set a long random JWT_SECRET before running in production")
    counts = init_db(engine, Path(settings.data_dir))
    log.info("Database ready: %s", counts)
    app.state.db_counts = counts
    if settings.fitbot_load_model and getattr(app.state, "chat_engine", None) is None:
        app.state.chat_engine, app.state.engine_info = build_engine(settings)
        log.info("FitBot engine ready: %s", {k: v for k, v in app.state.engine_info.items() if k != "slm"})
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan,
                  description="FitBot – a fitness-domain small language model assistant. "
                              "FitBot provides general fitness and wellness information and is not a substitute "
                              "for professional medical advice.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    for r in (auth.router, conversations.router, chat.router, catalog_routes.router):
        app.include_router(r)

    @app.get("/health", tags=["health"])
    def health(request: Request):
        info = getattr(request.app.state, "engine_info", None)
        return {"status": "ok" if info else "loading", "database": getattr(request.app.state, "db_counts", None),
                "engine": info}

    # Serve the built React app (frontend/dist) from the same origin when it exists (production).
    dist = Path(settings.frontend_dist)
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            f = (dist / full_path).resolve()
            if full_path and f.is_file() and dist.resolve() in f.parents:
                return FileResponse(f)           # favicon.svg etc.
            return FileResponse(dist / "index.html")   # client-side routes: /login, /chat/3, ...

    return StripApiPrefix(app)


app = create_app()
fastapi_app = app.app  # the FastAPI instance behind the prefix middleware
