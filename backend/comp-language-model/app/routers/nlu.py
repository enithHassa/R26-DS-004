"""NLU + retrieval baseline routes (Phase 2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.config import LanguageModelSettings, get_lm_settings
from app.schemas.nlu_v1 import NLUParseRequest, NLUParseResponse, RetrievalHit
from app.services.intent_benchmark import build_intent_classifier
from app.services.intent_tfidf_centroid import TfidfIntentCentroidClassifier
from app.services.tfidf_chunk_index import TfidfChunkIndex
from backend.shared.utils.logging import logger

router = APIRouter(prefix="/api/v1/nlu", tags=["nlu"])


def _predict_intent(
    clf: TfidfIntentCentroidClassifier | None, utterance: str
) -> tuple[str | None, str | None]:
    if clf is None:
        return None, None
    pred = clf.predict([utterance])[0]
    return pred, "tfidf-centroid"


@router.post("/parse", response_model=NLUParseResponse)
def parse_nlu(request: Request, body: NLUParseRequest) -> NLUParseResponse:
    index = getattr(request.app.state, "retrieval_index", None)
    clf: TfidfIntentCentroidClassifier | None = getattr(request.app.state, "intent_classifier", None)
    settings = get_lm_settings()
    k = body.top_k or settings.COMP_LLM_RETRIEVAL_TOP_K

    pred_intent, intent_model = _predict_intent(clf, body.utterance)

    if index is None:
        return NLUParseResponse(
            utterance=body.utterance,
            intent=body.intent_hint,
            predicted_intent=pred_intent,
            intent_model=intent_model,
            retrieval_hits=[],
            model="stub-no-corpus",
            corpus_loaded=False,
        )

    hits = index.search(body.utterance, k)
    if settings.COMP_LLM_RETRIEVAL_BACKEND == "dense":
        model_id = "dense-baseline"
    else:
        model_id = "tfidf-baseline"
    join_map: dict[str, dict[str, str | None]] = getattr(
        request.app.state, "chunk_kg_join_by_id", None
    ) or {}

    def _hit(cid: str, s: float) -> RetrievalHit:
        m = join_map.get(cid) or {}
        return RetrievalHit(
            chunk_id=cid,
            score=s,
            source_doc_id=m.get("source_doc_id"),
            section_uid=m.get("section_uid"),
            section_label=m.get("section_label"),
            tier=m.get("tier"),
            instrument_type=m.get("instrument_type"),
            content_kind=m.get("content_kind"),
        )

    return NLUParseResponse(
        utterance=body.utterance,
        intent=body.intent_hint,
        predicted_intent=pred_intent,
        intent_model=intent_model,
        retrieval_hits=[_hit(cid, s) for cid, s in hits],
        model=model_id,
        corpus_loaded=True,
    )


def attach_retrieval_index(app_state: Any, settings: LanguageModelSettings) -> None:
    """Load TF-IDF or dense chunk index into ``app.state.retrieval_index`` (lifespan)."""
    from pathlib import Path

    app_state.retrieval_from_embedding_bundle = False
    p = settings.COMP_LLM_CORPUS_JSONL
    if p is None or not Path(p).is_file():
        app_state.retrieval_index = None
        return

    path = Path(p)
    if settings.COMP_LLM_RETRIEVAL_BACKEND == "tfidf":
        app_state.retrieval_index = TfidfChunkIndex.from_jsonl(path)
        return

    from app.services.dense_chunk_index import DenseChunkIndex

    bundle_dir = settings.COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR
    if bundle_dir is not None:
        bpath = Path(bundle_dir)
        if bpath.is_dir():
            try:
                app_state.retrieval_index = DenseChunkIndex.from_embedding_bundle_dir(
                    bpath,
                    query_model_name=settings.COMP_LLM_DENSE_MODEL,
                )
                app_state.retrieval_from_embedding_bundle = True
                logger.info(
                    "Dense retrieval index loaded from embedding bundle (chunks={}, dir={})",
                    app_state.retrieval_index.size,
                    bpath,
                )
                return
            except Exception:
                logger.exception("Failed to load dense embedding bundle from %s; falling back to JSONL encode", bpath)

    try:
        app_state.retrieval_index = DenseChunkIndex.from_jsonl(
            path,
            model_name=settings.COMP_LLM_DENSE_MODEL,
            device=settings.COMP_LLM_DENSE_DEVICE,
        )
    except ImportError as exc:
        logger.warning(
            "Dense retrieval unavailable (install backend/requirements-retrieval-dense.txt): {}",
            exc,
        )
        app_state.retrieval_index = None
    except Exception:
        logger.exception("Failed to load dense chunk index")
        app_state.retrieval_index = None


def attach_intent_classifier(app_state: Any, path: Any) -> None:
    """Load TF-IDF centroid intent classifier from benchmark JSONL."""
    from pathlib import Path

    p = Path(path) if path is not None else None
    if p is None or not p.is_file():
        app_state.intent_classifier = None
        return
    app_state.intent_classifier = build_intent_classifier(p)
