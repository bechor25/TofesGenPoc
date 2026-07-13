"""Dependency providers. Store + job manager live on ``app.state`` (fresh per app,
so tests are isolated). LLM providers are built lazily and cached on ``app.state``;
tests swap them via ``app.dependency_overrides`` so no real API key is needed."""
from __future__ import annotations

from typing import cast

from fastapi import Request

from doc2tests.api.jobs import JobManager
from doc2tests.api.workspace import WorkspaceStore
from doc2tests.orchestrator.config import build_extract_provider, build_image_provider
from doc2tests.providers.base import LLMProvider


def get_store(request: Request) -> WorkspaceStore:
    return cast(WorkspaceStore, request.app.state.store)


def get_jobs(request: Request) -> JobManager:
    return cast(JobManager, request.app.state.jobs)


def get_extract_provider(request: Request) -> LLMProvider:
    state = request.app.state
    if getattr(state, "extract_provider", None) is None:
        state.extract_provider = build_extract_provider()
    return cast(LLMProvider, state.extract_provider)


def get_image_provider(request: Request) -> LLMProvider:
    state = request.app.state
    if getattr(state, "image_provider", None) is None:
        state.image_provider = build_image_provider()
    return cast(LLMProvider, state.image_provider)
