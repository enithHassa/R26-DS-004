"""CLI: ingest corpus PDFs and probe retrieve."""

from __future__ import annotations

import argparse
import json
import sys

from backend.shared.config.database import SessionLocal
from backend.shared.config.settings import PROJECT_ROOT
from oe_engine_app.config import get_oe_engine_settings
from oe_engine_app.services.embedder import OpenAIEmbedder
from oe_engine_app.services.extract import run_extract
from oe_engine_app.services.extract_llm import OpenAIExtractLLM
from oe_engine_app.services.ingest import ingest_manifest
from oe_engine_app.services.retrieve import hits_to_json, hybrid_retrieve
from oe_engine_app.services.shape import compare_entity_shape, first_of_kind
from oe_engine_app.services.spend import (
    PHASE6_HARD_STOP_USD,
    PHASE6_SOFT_CAP_USD,
    SpendLedger,
    load_phase6_prior,
)


def _embedder() -> OpenAIEmbedder:
    settings = get_oe_engine_settings()
    if not settings.OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY is not set")
    return OpenAIEmbedder(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OE_ENGINE_EMBEDDING_MODEL,
        batch_size=settings.OE_ENGINE_EMBED_BATCH_SIZE,
    )


def cmd_ingest(source_doc_id: str | None) -> int:
    embedder = _embedder()
    session = SessionLocal()
    try:
        results = ingest_manifest(session, embedder=embedder, source_doc_id=source_doc_id)
    finally:
        session.close()
    total_usd = 0.0
    for row in results:
        total_usd += row.embedding_usd
        print(
            f"{row.status:16} {row.source_doc_id:24} "
            f"chunks={row.chunk_count:<5} pages={row.page_count:<4} "
            f"usd~{row.embedding_usd:.4f} {row.detail}"
        )
    print(f"embedding_usd_estimate_total={total_usd:.4f}")
    missing = [row for row in results if row.status == "missing_pdf"]
    return 1 if missing else 0


def cmd_retrieve(query: str, source_doc_id: str | None, top_k: int) -> int:
    settings = get_oe_engine_settings()
    session = SessionLocal()
    try:
        embedding = None
        if settings.OPENAI_API_KEY:
            embedding = _embedder().embed_batch([query])[0]
        hits = hybrid_retrieve(
            session,
            query=query,
            query_embedding=embedding,
            source_doc_id=source_doc_id,
            top_k=top_k,
        )
    finally:
        session.close()
    print(json.dumps({"query": query, "hit_count": len(hits), "hits": hits_to_json(hits)}, indent=2))
    return 0 if hits else 2


def _print_run(run: object) -> None:
    payload = run.model_dump(mode="json")  # type: ignore[attr-defined]
    print(f"source_doc_id={payload['source_doc_id']}")
    print(f"tier={payload['tier']}  terminus={payload['terminus']}")
    print(f"dry_run={payload['dry_run']}  model={payload['model']}")
    print(
        f"usd_this_run={payload['usd_this_run']:.4f}  "
        f"usd_running_total={payload['usd_running_total']:.4f}"
    )
    print(f"windows={len(payload['windows'])}  entities={len(payload['entities'])}")
    for window in payload["windows"]:
        print(
            f"  {window['window_id']:20} chars={window['char_count']:<5} "
            f"pages={window.get('page_start')}-{window.get('page_end')}  "
            f"{window['heading']}"
        )
    for note in payload.get("notes") or []:
        print(f"  note: {note}")


def _planned_fixture(kind: str) -> dict:
    path = (
        PROJECT_ROOT
        / "models"
        / "opt-explain-engine"
        / "fixtures"
        / f"extract_schema_{kind}.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _print_shape_report(run: object) -> int:
    entities = run.entities  # type: ignore[attr-defined]
    kinds = ("relief", "rate_band")
    ok = True
    report: dict = {"extraction_run_id": run.extraction_run_id, "windows": []}  # type: ignore[attr-defined]
    for kind in kinds:
        actual = first_of_kind(entities, kind)
        planned = _planned_fixture(kind)
        if actual is None:
            print(f"SHAPE FAIL: no {kind} entity in extract output")
            ok = False
            report[kind] = {"ok": False, "error": "missing entity"}
            continue
        compared = compare_entity_shape(actual, planned)
        report[kind] = compared
        status = "OK" if compared["ok"] else "FAIL"
        print(f"SHAPE {status} {kind}: missing={compared['missing_keys']} extra={compared['extra_keys']}")
        if not compared["ok"]:
            ok = False
    out = PROJECT_ROOT / "models" / "opt-explain-engine" / "extracted" / "schema_validation_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"shape_report={out.as_posix()}")
    return 0 if ok else 3


def _print_spend_caps(ledger: SpendLedger) -> None:
    print(
        f"USD this doc=${ledger.this_run_usd:.4f}  "
        f"running=${ledger.total_usd:.4f}  "
        f"soft=${PHASE6_SOFT_CAP_USD:.0f}  hard=${PHASE6_HARD_STOP_USD:.0f}  "
        f"budget={ledger.budget}"
    )
    if ledger.budget == "phase6_seed" and ledger.total_usd >= PHASE6_SOFT_CAP_USD:
        print(
            "STOP: running total is at or past the $15 soft cap. "
            "Do not start the next PDF (Guide is optional).",
            file=sys.stderr,
        )


def _print_quote_gate_sample(run: object) -> None:
    entities = list(getattr(run, "entities", None) or [])
    included = [e for e in entities if e.get("included")]
    excluded = [e for e in entities if not e.get("included")]
    print(f"quote-gate included={len(included)}  excluded={len(excluded)}  total={len(entities)}")
    individual = [e for e in entities if e.get("engine_scope") == "individual"]
    other = [e for e in entities if e.get("engine_scope") == "other"]
    print(
        f"engine_scope individual={len(individual)}  other={len(other)}  "
        "(other never promotes)"
    )
    print("--- sample included (up to 8) ---")
    for entity in included[:8]:
        cap = entity.get("cap_amount") or entity.get("rate_percent") or ""
        quote = (entity.get("quote") or "").replace("\n", " ")[:160]
        print(
            f"  IN  {entity.get('entity_kind')}  "
            f"{entity.get('compare_group_id')}  "
            f"scope={entity.get('engine_scope') or '-'}  "
            f"cap/rate={cap}  from={entity.get('effective_from') or '-'}  "
            f"q_win={entity.get('quote_ok_window')}  "
            f"q_doc={entity.get('quote_ok_full_doc')}  "
            f"p2={entity.get('pass2_verbatim')}"
        )
        print(f"      quote: {quote}")
    print("--- sample excluded (up to 5) ---")
    for entity in excluded[:5]:
        quote = (entity.get("quote") or "").replace("\n", " ")[:120]
        print(
            f"  OUT {entity.get('entity_kind')}  "
            f"{entity.get('compare_group_id')}  "
            f"q_win={entity.get('quote_ok_window')}  "
            f"q_doc={entity.get('quote_ok_full_doc')}  "
            f"p2={entity.get('pass2_verbatim')}  "
            f"note={entity.get('pass2_note') or '-'}"
        )
        print(f"      quote: {quote}")


def cmd_extract(
    source_doc_id: str,
    *,
    dry_run: bool,
    schema_validate: bool,
    seed: bool = False,
) -> int:
    settings = get_oe_engine_settings()
    if seed:
        prior = load_phase6_prior()
        ledger = SpendLedger(budget="phase6_seed", prior_usd=prior)
        print(
            f"phase6_seed prior=${prior:.4f}  "
            f"soft=${PHASE6_SOFT_CAP_USD:.0f}  hard=${PHASE6_HARD_STOP_USD:.0f}"
        )
        if prior >= PHASE6_SOFT_CAP_USD:
            print(
                "STOP: running total already at/past $15 soft cap. Not extracting.",
                file=sys.stderr,
            )
            return 6
    elif schema_validate:
        ledger = SpendLedger(budget="phase3_schema_validation")
    else:
        ledger = SpendLedger(budget="phase3_dry_run")
    llm = None
    if not dry_run:
        if not settings.OPENAI_API_KEY:
            raise SystemExit("OPENAI_API_KEY is not set")
        from openai import OpenAI

        llm = OpenAIExtractLLM(
            OpenAI(api_key=settings.OPENAI_API_KEY),
            model=settings.OE_ENGINE_EXTRACT_MODEL,
            ledger=ledger,
        )
    session = SessionLocal()
    try:
        try:
            run = run_extract(
                session,
                source_doc_id=source_doc_id,
                llm=llm,
                ledger=ledger,
                dry_run=dry_run,
                schema_validate=schema_validate,
                seed=seed,
            )
        except RuntimeError as exc:
            ledger.dump()
            _print_spend_caps(ledger)
            message = str(exc)
            if "OPENAI_CREDITS_EXHAUSTED" in message or "OPENAI_AUTH_FAILED" in message:
                print(
                    "STOP: OpenAI quota or auth failed. Do not retry. "
                    "Load credits / fix the key, then resume this same document.",
                    file=sys.stderr,
                )
                print(message, file=sys.stderr)
                return 4
            if "hard stop" in message.lower():
                print("STOP: $40 hard stop. Do not retry.", file=sys.stderr)
                print(message, file=sys.stderr)
                return 5
            raise
    finally:
        session.close()
    _print_run(run)
    _print_spend_caps(ledger)
    if not dry_run:
        _print_quote_gate_sample(run)
    if schema_validate and not dry_run:
        return _print_shape_report(run)
    if seed and ledger.total_usd >= PHASE6_SOFT_CAP_USD:
        return 6
    return 0


def cmd_regate(source_doc_id: str, dry_run: bool) -> int:
    from oe_engine_app.services.regate import regate_extract

    session = SessionLocal()
    try:
        result = regate_extract(session, source_doc_id, write=not dry_run)
    finally:
        session.close()
    print(json.dumps(result, default=str, indent=2))
    return 0


def cmd_reextract_window(source_doc_id: str, window_id: str, dry_run: bool) -> int:
    from oe_engine_app.services.reextract_window import reextract_window
    from oe_engine_app.services.windows import extract_focus_windows, load_doc_text

    session = SessionLocal()
    try:
        if dry_run:
            doc = load_doc_text(session, source_doc_id)
            windows = {w.window_id: w for w in extract_focus_windows(doc)}
            window = windows.get(window_id)
            if window is None:
                print(f"unknown window {window_id!r}; have {sorted(windows)}", file=sys.stderr)
                return 2
            print(f"{window.window_id}  {window.heading}  chars={window.char_count}")
            print(window.text)
            return 0
        settings = get_oe_engine_settings()
        if not settings.OPENAI_API_KEY:
            raise SystemExit("OPENAI_API_KEY is not set")
        from openai import OpenAI

        ledger = SpendLedger(budget="phase3_schema_validation")
        llm = OpenAIExtractLLM(
            OpenAI(api_key=settings.OPENAI_API_KEY),
            model=settings.OE_ENGINE_EXTRACT_MODEL,
            ledger=ledger,
        )
        result = reextract_window(
            session,
            source_doc_id=source_doc_id,
            window_id=window_id,
            llm=llm,
        )
    finally:
        session.close()
    print(json.dumps(result, default=str, indent=2))
    _print_spend_caps(ledger)
    return 0


def cmd_promote(source_doc_id: str, extraction_run_id: str | None) -> int:
    from oe_engine_app.services.fixtures import load_promote_run
    from oe_engine_app.services.terminus import promote_act_run

    session = SessionLocal()
    try:
        run = load_promote_run(source_doc_id, extraction_run_id)
        result = promote_act_run(session, run)
        session.commit()
    finally:
        session.close()
    print(json.dumps(result, default=str, indent=2))
    return 0


def cmd_promote_fixture() -> int:
    from oe_engine_app.services.fixtures import load_extract_fixture, seed_act_document
    from oe_engine_app.services.terminus import promote_act_run
    from oe_engine_app.services.year_store import list_years

    session = SessionLocal()
    try:
        seed_act_document(
            session, source_doc_id="oee-fixture-act-2022", title="Fixture Act 2022"
        )
        seed_act_document(
            session, source_doc_id="oee-fixture-act-2025", title="Fixture Act 2025"
        )
        older = load_extract_fixture("act_extract_2022.json")
        newer = load_extract_fixture("act_extract_2025.json")
        print(promote_act_run(session, older))
        print(promote_act_run(session, newer))
        session.commit()
        years = list_years(session)
        print(json.dumps({"years": years, "year_count": len(years)}, indent=2))
    finally:
        session.close()
    return 0


def cmd_unpromote(source_doc_id: str, *, reset_act_admin: bool) -> int:
    from oe_engine_app.services.act_admin_review import reset_activation
    from oe_engine_app.services.terminus import unpromote_source_doc
    from oe_engine_app.services.year_store import list_years

    session = SessionLocal()
    try:
        result = unpromote_source_doc(session, source_doc_id)
        session.commit()
        years = [row["assessment_year"] for row in list_years(session)]
    finally:
        session.close()
    if reset_act_admin:
        result["act_admin"] = reset_activation(source_doc_id, reviewer="cli-unpromote")
    result["years"] = years
    print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oe_engine_app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ingest_p = sub.add_parser("ingest", help="Ingest corpus PDFs (skip by sha256)")
    ingest_p.add_argument("--source-doc-id", default=None)

    retrieve_p = sub.add_parser("retrieve", help="Hybrid retrieve against ingested chunks")
    retrieve_p.add_argument("--query", required=True)
    retrieve_p.add_argument("--source-doc-id", default=None)
    retrieve_p.add_argument("--top-k", type=int, default=8)

    extract_p = sub.add_parser(
        "extract",
        help="Windowed GPT-4o extract (--dry-run, --schema-validate, or Phase 6 --seed)",
    )
    extract_p.add_argument("--source-doc-id", required=True)
    extract_p.add_argument("--dry-run", action="store_true")
    extract_p.add_argument(
        "--schema-validate",
        action="store_true",
        help="Live Fifth Schedule + First Schedule windows on one Act (not full-doc seed)",
    )
    extract_p.add_argument(
        "--seed",
        action="store_true",
        help="Phase 6 full-document live extract (one PDF). Counts toward $15/$40.",
    )

    regate_p = sub.add_parser(
        "regate",
        help="Replay the quote gate over a stored extract ($0, no GPT)",
    )
    regate_p.add_argument("--source-doc-id", required=True)
    regate_p.add_argument("--dry-run", action="store_true")

    rewin_p = sub.add_parser(
        "reextract-window",
        help="Re-run GPT-4o on one focus window and merge it into the stored extract",
    )
    rewin_p.add_argument("--source-doc-id", required=True)
    rewin_p.add_argument("--window-id", required=True)
    rewin_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the window text and exit ($0, no GPT call)",
    )

    promote_p = sub.add_parser(
        "promote",
        help="Promote a reviewed Act extract into year views (no GPT)",
    )
    promote_p.add_argument("--source-doc-id", required=True)
    promote_p.add_argument("--extraction-run-id", default=None)

    sub.add_parser(
        "promote-fixture",
        help="Promote hand-built Act fixtures into year views ($0, no GPT)",
    )

    unpromote_p = sub.add_parser(
        "unpromote",
        help="Remove one Act from year views and drop YA 2026/27 if it was only NEW_YEAR",
    )
    unpromote_p.add_argument("--source-doc-id", required=True)
    unpromote_p.add_argument(
        "--reset-act-admin",
        action="store_true",
        help="Put the act-admin draft back to extracted so Activate can be demoed again",
    )

    args = parser.parse_args(argv)
    if args.cmd == "ingest":
        return cmd_ingest(args.source_doc_id)
    if args.cmd == "retrieve":
        return cmd_retrieve(args.query, args.source_doc_id, args.top_k)
    if args.cmd == "extract":
        seed = bool(args.seed)
        schema_validate = bool(args.schema_validate) and not seed
        if seed and args.schema_validate:
            print(
                "--seed takes precedence over --schema-validate (full document).",
                file=sys.stderr,
            )
        if not args.dry_run and not schema_validate and not seed:
            print(
                "Full-document live extract is Phase 6. "
                "Pass --dry-run, --schema-validate, or --seed.",
                file=sys.stderr,
            )
            return 2
        return cmd_extract(
            args.source_doc_id,
            dry_run=args.dry_run,
            schema_validate=schema_validate,
            seed=seed,
        )
    if args.cmd == "regate":
        return cmd_regate(args.source_doc_id, bool(args.dry_run))
    if args.cmd == "reextract-window":
        return cmd_reextract_window(
            args.source_doc_id, args.window_id, bool(args.dry_run)
        )
    if args.cmd == "promote":
        return cmd_promote(args.source_doc_id, args.extraction_run_id)
    if args.cmd == "promote-fixture":
        return cmd_promote_fixture()
    if args.cmd == "unpromote":
        return cmd_unpromote(args.source_doc_id, reset_act_admin=bool(args.reset_act_admin))
    return 1


if __name__ == "__main__":
    sys.exit(main())
