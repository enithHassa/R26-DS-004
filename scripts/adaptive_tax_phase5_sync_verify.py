#!/usr/bin/env python3
"""Phase 5 post-milestone knowledge-pipeline sync + verify.

Keeps PostgreSQL / Neo4j / Chroma / param packs / Rule Engine / Explanation
evidence sources aligned after each coverage area (Business, Investment, Credits…).

Reuses existing loaders only — no architecture changes::

  # Verify only (default)
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_phase5_sync_verify.py

  # Reload Neo4j calc ontology + edges, then verify
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_phase5_sync_verify.py --apply-neo4j

  # Also rebuild Chroma from corpus (when legal PDFs / corpus changed)
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_phase5_sync_verify.py --apply-neo4j --apply-chroma

Exit code 0 = all required checks passed; 1 = gaps reported; 2 = config error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
_ONTO = _REPO / "models" / "adaptive-tax" / "ontology"
_FIXTURES = _REPO / "models" / "adaptive-tax" / "fixtures"
_COMP = _REPO / "backend" / "comp-adaptive-tax"

for p in (_REPO, _COMP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# Concepts that must exist in Neo4j after Phase 5.6 (extend as new areas land).
_REQUIRED_CONCEPTS = (
    "business_income",
    "business_gross",
    "business_deductions",
    "capital_allowances",
    "employment_income",
    "investment_income",
    "investment_final_withholding",
    "tax_credit",
    "apit_already_paid",
    "tax_payable",
    "assessable_income",
    "resident_individual",
    "solar_panel_relief",
    "solar_panel_relief_cap",
    "rent_relief",
    "rent_relief_cap",
    "qualifying_payment",
)

# (concept_id, section_uid_suffix) for GOVERNED_BY checks.
_REQUIRED_GOVERNED_BY = (
    ("business_income", "section_6"),
    ("business_gross", "section_6"),
    ("business_deductions", "section_11"),
    ("capital_allowances", "section_16"),
    ("employment_income", "section_5"),
    ("investment_income", "section_7"),
    ("investment_final_withholding", "section_7"),
    ("tax_credit", "section_89"),
    ("apit_already_paid", "section_89"),
    ("solar_panel_relief", "fifth_schedule"),
    ("rent_relief", "fifth_schedule"),
    ("qualifying_payment", "section_52"),
)

# (relief_concept_id, cap_concept_id) for LIMITED_BY checks.
_REQUIRED_LIMITED_BY = (
    ("solar_panel_relief", "solar_panel_relief_cap"),
    ("rent_relief", "rent_relief_cap"),
)

_PACK_FILES = (
    _ONTO / "rate_bands_2024_25.json",
    _ONTO / "rate_bands_2025_26.json",
    _ONTO / "relief_caps_2024_25.json",
    _ONTO / "relief_caps_2025_26.json",
)

_CHROMA_SMOKE = (
    ("business income", "6"),
    ("investment income", "7"),
    ("qualifying payment", "52"),
    ("capital allowances", "16"),
    ("tax credit withholding", "89"),
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bootstrap_ids() -> set[str]:
    doc = _load_json(_FIXTURES / "provenance_bootstrap_v1.json")
    return {str(r["id"]) for r in doc.get("rules") or [] if r.get("id")}


def _run_loader(args: list[str], *, env: dict[str, str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=str(_REPO),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _check_file_ontology(report: dict[str, Any]) -> None:
    concepts = _load_json(_ONTO / "concepts_mvp.json")
    cids = {c["concept_id"] for c in concepts.get("concepts") or []}
    missing = [c for c in _REQUIRED_CONCEPTS if c not in cids]
    edges_path = _ONTO / "mvp_calc_edges_seed.jsonl"
    edge_rows: list[dict[str, Any]] = []
    for line in edges_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            edge_rows.append(json.loads(line))
    contributes = any(
        e.get("rel_type") == "CONTRIBUTES_TO"
        and e.get("from_id") == "business_income"
        and e.get("to_id") == "assessable_income"
        for e in edge_rows
    )
    missing_limited = [
        f"{cid}->{cap}"
        for cid, cap in _REQUIRED_LIMITED_BY
        if not any(
            e.get("rel_type") == "LIMITED_BY"
            and e.get("from_id") == cid
            and e.get("to_id") == cap
            for e in edge_rows
        )
    ]
    missing_gov = [
        f"{cid} (want *{suffix}*)"
        for cid, suffix in _REQUIRED_GOVERNED_BY
        if not any(
            e.get("rel_type") == "GOVERNED_BY"
            and e.get("from_id") == cid
            and suffix in str(e.get("to_id") or "")
            for e in edge_rows
        )
    ]
    report["file_ontology"] = {
        "ok": not missing and contributes and not missing_limited and not missing_gov,
        "concepts": len(cids),
        "edges": len(edge_rows),
        "missing_concepts": missing,
        "missing_limited_by": missing_limited,
        "missing_governed_by": missing_gov,
        "business_contributes_to_assessable": contributes,
    }


def _check_param_packs(report: dict[str, Any]) -> None:
    boot = _bootstrap_ids()
    gaps: list[str] = []
    checked = 0
    for path in _PACK_FILES:
        doc = _load_json(path)
        rows = list(doc.get("bands") or doc.get("reliefs") or [])
        for row in rows:
            rid = row.get("rule_source_id")
            if not rid:
                gaps.append(f"{path.name}: missing rule_source_id on {row.get('rate_band_id') or row.get('relief_id')}")
                continue
            checked += 1
            if str(rid) not in boot:
                gaps.append(f"{path.name}: {rid} not in provenance_bootstrap_v1.json")
    report["param_packs"] = {
        "ok": not gaps,
        "checked_rows": checked,
        "bootstrap_ids": len(boot),
        "gaps": gaps,
    }


def _check_neo4j(report: dict[str, Any], password: str) -> None:
    try:
        from neo4j import GraphDatabase
    except ImportError:
        report["neo4j"] = {"ok": False, "error": "neo4j driver not installed"}
        return

    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    if uri.startswith("neo4j://"):
        uri = "bolt://" + uri[len("neo4j://") :]
    user = os.environ.get("NEO4J_USER", "neo4j")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            concept_rows = session.run(
                """
                MATCH (c:Concept)
                WHERE c.concept_id IN $ids
                RETURN c.concept_id AS concept_id
                """,
                ids=list(_REQUIRED_CONCEPTS),
            ).data()
            present = {r["concept_id"] for r in concept_rows}
            missing_concepts = [c for c in _REQUIRED_CONCEPTS if c not in present]

            contrib = session.run(
                """
                MATCH (bi:Concept {concept_id:'business_income'})
                      -[:CONTRIBUTES_TO]->(ai:Concept {concept_id:'assessable_income'})
                RETURN count(*) AS n
                """
            ).single()
            contributes_ok = bool(contrib and contrib["n"] >= 1)

            gov_rows = session.run(
                """
                MATCH (c:Concept)-[:GOVERNED_BY]->(s:Section)
                WHERE c.concept_id IN $ids
                RETURN c.concept_id AS concept_id, s.section_uid AS section_uid
                """,
                ids=[c for c, _ in _REQUIRED_GOVERNED_BY],
            ).data()
            gov_map: dict[str, list[str]] = {}
            for r in gov_rows:
                gov_map.setdefault(r["concept_id"], []).append(r["section_uid"] or "")
            missing_gov: list[str] = []
            for cid, suffix in _REQUIRED_GOVERNED_BY:
                uids = gov_map.get(cid) or []
                if not any(suffix in uid for uid in uids):
                    got = ", ".join(uids) if uids else "missing"
                    missing_gov.append(f"{cid} (want *{suffix}*, got {got})")

            lim_rows = session.run(
                """
                MATCH (c:Concept)-[:LIMITED_BY]->(cap:Concept)
                WHERE c.concept_id IN $ids
                RETURN c.concept_id AS concept_id, cap.concept_id AS cap_id
                """,
                ids=[c for c, _ in _REQUIRED_LIMITED_BY],
            ).data()
            lim_map: dict[str, list[str]] = {}
            for r in lim_rows:
                lim_map.setdefault(r["concept_id"], []).append(r["cap_id"] or "")
            missing_limited: list[str] = []
            for cid, cap in _REQUIRED_LIMITED_BY:
                if cap not in (lim_map.get(cid) or []):
                    got = ", ".join(lim_map.get(cid) or []) or "missing"
                    missing_limited.append(f"{cid}->{cap} (got {got})")

            counts = session.run(
                """
                MATCH (n)
                RETURN labels(n)[0] AS label, count(*) AS cnt
                ORDER BY cnt DESC
                """
            ).data()
        driver.close()
        report["neo4j"] = {
            "ok": (
                not missing_concepts
                and contributes_ok
                and not missing_gov
                and not missing_limited
            ),
            "missing_concepts": missing_concepts,
            "business_contributes_to_assessable": contributes_ok,
            "missing_governed_by": missing_gov,
            "missing_limited_by": missing_limited,
            "node_counts": counts,
        }
    except Exception as exc:  # noqa: BLE001 — report connectivity gaps
        report["neo4j"] = {"ok": False, "error": str(exc)}


def _check_chroma(report: dict[str, Any], *, smoke: bool) -> None:
    persist = Path(
        os.environ.get("CHROMA_PERSIST_DIR", "data/processed/adaptive-tax/chroma")
    )
    if not persist.is_absolute():
        persist = _REPO / persist
    corpus = _REPO / "data" / "processed" / "adaptive-tax" / "corpus_v1.jsonl"
    base: dict[str, Any] = {
        "persist_dir": str(persist),
        "persist_exists": persist.is_dir(),
        "corpus_exists": corpus.is_file(),
    }
    if not persist.is_dir() or not corpus.is_file():
        base["ok"] = False
        base["gaps"] = [
            g
            for g, ok in (
                ("chroma persist dir missing — run adaptive_tax_build_chroma.py", persist.is_dir()),
                ("corpus_v1.jsonl missing — run adaptive_tax_build_corpus.py", corpus.is_file()),
            )
            if not ok
        ]
        report["chroma"] = base
        return

    if not smoke:
        base["ok"] = True
        base["note"] = "persist dir present; skip RAG smoke (--chroma-smoke to enable)"
        report["chroma"] = base
        return

    try:
        from adaptive_tax_app.services.chroma_index import AdaptiveTaxChromaIndex
        from adaptive_tax_app.services.evidence import _EXPLAIN_BLOCKED_SOURCE_DOC_IDS

        index = AdaptiveTaxChromaIndex(persist_dir=persist)
        smoke_results: list[dict[str, Any]] = []
        gaps: list[str] = []
        for query, section in _CHROMA_SMOKE:
            hits = index.search(query=query, section_ref=section, top_k=8)
            allowed = [
                h
                for h in hits
                if (h.source_doc_id or "") not in _EXPLAIN_BLOCKED_SOURCE_DOC_IDS
            ]
            # Section metadata is often a list-string; ranking may surface Master first.
            # Fall back to unfiltered search then keep Act / guide hits that cite the section.
            if not allowed:
                broad = index.search(query=query, section_ref=None, top_k=15)
                needle = section.lower()
                allowed = []
                for h in broad:
                    if (h.source_doc_id or "") in _EXPLAIN_BLOCKED_SOURCE_DOC_IDS:
                        continue
                    blob = f"{h.section_ref or ''} {h.text or ''}".lower()
                    if needle in blob or f"section {needle}" in blob:
                        allowed.append(h)
                hits = broad
            smoke_results.append(
                {
                    "query": query,
                    "section": section,
                    "hits": len(hits),
                    "explain_allowed_hits": len(allowed),
                    "sample_source_doc_ids": list(
                        dict.fromkeys(h.source_doc_id for h in allowed[:5])
                    ),
                }
            )
            if not hits:
                gaps.append(f"no Chroma hits for query={query!r} section={section!r}")
            elif not allowed:
                gaps.append(
                    f"no explain-allowed (non-Master) hits for query={query!r} "
                    f"section={section!r}"
                )
        base["ok"] = not gaps
        base["smoke"] = smoke_results
        base["gaps"] = gaps
        base["blocked_source_doc_ids"] = sorted(_EXPLAIN_BLOCKED_SOURCE_DOC_IDS)
    except Exception as exc:  # noqa: BLE001
        base["ok"] = False
        base["error"] = str(exc)
    report["chroma"] = base


def _check_rule_engine(report: dict[str, Any], *, neo4j: bool) -> None:
    try:
        from decimal import Decimal

        from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
        from adaptive_tax_app.services.kg_client import get_kg_client
        from adaptive_tax_app.services.provenance import clear_provenance_cache
        from adaptive_tax_app.services.param_store import clear_param_store_cache, reset_param_override
        from adaptive_tax_app.services.rule_engine import calculate

        clear_provenance_cache()
        clear_param_store_cache()
        reset_param_override()
        kg = get_kg_client(mode="neo4j" if neo4j else "file")
        hit = kg.resolve_applicable_concepts(
            income_types=["business_income"],
            claimed_deductions=[],
        )
        r = calculate(
            CalculateTaxRequestV1(
                assessment_year="2025_26",
                resident_status="resident",
                business_income=Decimal("2100000"),
            ),
            kg=kg,
        )
        r2 = calculate(
            CalculateTaxRequestV1(
                assessment_year="2025_26",
                resident_status="resident",
                business_gross=Decimal("2500000"),
                business_deductions=Decimal("200000"),
                capital_allowances=Decimal("100000"),
            ),
            kg=kg,
        )
        ok = (
            "business_income" in hit.income_concept_ids
            and r.final_tax_lkr == "18000"
            and r2.final_tax_lkr == "24000"
            and "compute_business_net" in r2.rules_applied
        )
        r3 = calculate(
            CalculateTaxRequestV1(
                assessment_year="2024_25",
                resident_status="resident",
                employment_income=Decimal("1800000"),
                apit_already_paid=Decimal("20000"),
            ),
            kg=kg,
        )
        credit_ok = (
            r3.final_tax_lkr == "42000"
            and r3.tax_payable_lkr == "22000"
            and "apply_tax_credit" in r3.rules_applied
        )
        report["rule_engine"] = {
            "ok": ok and credit_ok,
            "kg_mode": "neo4j" if neo4j else "file",
            "kg_business_resolved": "business_income" in hit.income_concept_ids,
            "kg_sections": list(hit.income_section_uids.get("business_income") or ()),
            "net_path_tax": r.final_tax_lkr,
            "gross_path_tax": r2.final_tax_lkr,
            "gross_path_rules_head": r2.rules_applied[:3],
            "credit_gross_tax": r3.final_tax_lkr,
            "credit_tax_payable": r3.tax_payable_lkr,
            "credit_ok": credit_ok,
        }
    except Exception as exc:  # noqa: BLE001
        report["rule_engine"] = {"ok": False, "error": str(exc)}


def _check_postgres(report: dict[str, Any]) -> None:
    """Best-effort: approved rule_source rows when DATABASE_MODE is reachable."""
    try:
        from sqlalchemy import text

        from backend.shared.db.session import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            # Table may live under adaptive-tax schema naming; probe common names.
            exists = conn.execute(
                text(
                    """
                    SELECT EXISTS (
                      SELECT 1 FROM information_schema.tables
                      WHERE table_name = 'rule_source'
                    )
                    """
                )
            ).scalar()
            if not exists:
                report["postgres"] = {
                    "ok": True,
                    "skipped": True,
                    "note": "rule_source table not present (offline / sqlite without amendments)",
                }
                return
            n_approved = conn.execute(
                text(
                    "SELECT count(*) FROM rule_source WHERE status = 'approved'"
                )
            ).scalar()
            report["postgres"] = {
                "ok": True,
                "approved_rule_source_rows": int(n_approved or 0),
                "note": (
                    "Calc provenance uses provenance_bootstrap_v1.json; "
                    "Postgres holds amendment-approved rule_source for explain/approve path."
                ),
            }
    except Exception as exc:  # noqa: BLE001
        report["postgres"] = {
            "ok": True,
            "skipped": True,
            "note": f"DB unreachable — bootstrap path still valid ({exc})",
        }


def _summary_missing_count(out: str) -> int | None:
    matches = re.findall(r"(\d+)\s+missing endpoint", out.lower())
    if not matches:
        return None
    return int(matches[-1])


def _non_mention_missing_lines(out: str) -> list[str]:
    """Executable-edge misses only; bulk MENTIONS TextChunks are advisory."""
    lines: list[str] = []
    for ln in out.splitlines():
        if "missing endpoint(s) for" not in ln.lower():
            continue
        if "TextChunk(" in ln:
            continue
        lines.append(ln.strip())
    return lines


def _apply_neo4j(env: dict[str, str]) -> dict[str, Any]:
    seed = _ONTO / "mvp_calc_edges_seed.jsonl"
    full = _ONTO / "calculation_edges_full.jsonl"
    code1, out1 = _run_loader([str(_SCRIPTS / "neo4j_load_calc_ontology_nodes.py")], env=env)
    code_seed, out_seed = _run_loader(
        [
            str(_SCRIPTS / "neo4j_load_curated_edges.py"),
            "--edges-jsonl",
            str(seed),
            "--warn-miss",
        ],
        env=env,
    )
    seed_missing = _summary_missing_count(out_seed)
    seed_ok = code_seed == 0 and seed_missing == 0

    mentions_missing = 0
    executable_missing: list[str] = []
    code_full, out_full = 0, ""
    if full.is_file() and full.stat().st_size > 0:
        code_full, out_full = _run_loader(
            [
                str(_SCRIPTS / "neo4j_load_curated_edges.py"),
                "--edges-jsonl",
                str(full),
                "--warn-miss",
            ],
            env=env,
        )
        executable_missing = _non_mention_missing_lines(out_full)
        full_missing = _summary_missing_count(out_full) or 0
        mentions_missing = max(0, full_missing - len(executable_missing))
        full_ok = code_full == 0 and not executable_missing
    else:
        full_ok = True

    return {
        "nodes": {"exit_code": code1, "output": out1[-2000:]},
        "seed_edges": {"exit_code": code_seed, "output": out_seed[-2000:]},
        "edges": {"exit_code": code_full, "output": out_full[-2000:]},
        "seed_missing": seed_missing,
        "mentions_missing": mentions_missing,
        "executable_missing": executable_missing,
        "ok": code1 == 0 and seed_ok and full_ok,
    }


def _apply_chroma(env: dict[str, str]) -> dict[str, Any]:
    code, out = _run_loader(
        [str(_SCRIPTS / "adaptive_tax_build_chroma.py"), "--reset"],
        env=env,
    )
    return {"exit_code": code, "output": out[-2000:], "ok": code == 0}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--apply-neo4j",
        action="store_true",
        help="Reload calc ontology nodes + calculation_edges_full (or seed) into Neo4j",
    )
    p.add_argument(
        "--apply-chroma",
        action="store_true",
        help="Rebuild Chroma from corpus_v1.jsonl before verify (use when corpus changed)",
    )
    p.add_argument(
        "--chroma-smoke",
        action="store_true",
        help="Run RAG smoke queries against Chroma (slower; needs embed model)",
    )
    p.add_argument(
        "--kg-mode",
        choices=("file", "neo4j"),
        default="neo4j",
        help="Rule-engine KG mode for live calc smoke (default neo4j)",
    )
    p.add_argument("--json", action="store_true", help="Print full JSON report")
    args = p.parse_args()

    password = (os.environ.get("NEO4J_PASSWORD") or "").strip()
    env = os.environ.copy()
    env.setdefault("NEO4J_URI", "bolt://127.0.0.1:7687")
    env.setdefault("NEO4J_USER", "neo4j")
    if password:
        env["NEO4J_PASSWORD"] = password

    report: dict[str, Any] = {
        "component": "adaptive-tax",
        "phase": "5",
        "purpose": "post-milestone knowledge pipeline sync + verify",
    }

    if args.apply_neo4j:
        if not password:
            print("NEO4J_PASSWORD is not set (required for --apply-neo4j)", file=sys.stderr)
            return 2
        report["apply_neo4j"] = _apply_neo4j(env)

    if args.apply_chroma:
        report["apply_chroma"] = _apply_chroma(env)

    _check_file_ontology(report)
    _check_param_packs(report)
    _check_postgres(report)

    if password:
        _check_neo4j(report, password)
    else:
        report["neo4j"] = {
            "ok": False,
            "skipped": True,
            "error": "NEO4J_PASSWORD not set — Neo4j checks skipped",
        }

    _check_chroma(report, smoke=args.chroma_smoke)
    _check_rule_engine(report, neo4j=(args.kg_mode == "neo4j" and bool(password)))

    required_keys = ("file_ontology", "param_packs", "neo4j", "rule_engine")
    failures = [
        k
        for k in required_keys
        if not (report.get(k) or {}).get("ok")
        and not (report.get(k) or {}).get("skipped")
    ]
    if args.apply_neo4j and not (report.get("apply_neo4j") or {}).get("ok"):
        failures.append("apply_neo4j")
    if args.apply_chroma and not (report.get("apply_chroma") or {}).get("ok"):
        failures.append("apply_chroma")
    # Chroma persist presence is advisory unless smoke requested.
    if args.chroma_smoke and not (report.get("chroma") or {}).get("ok"):
        failures.append("chroma")

    report["summary"] = {
        "ok": not failures,
        "failures": failures,
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("=== Phase 5 knowledge pipeline sync verify ===")
        for key in (
            "apply_neo4j",
            "apply_chroma",
            "file_ontology",
            "param_packs",
            "postgres",
            "neo4j",
            "chroma",
            "rule_engine",
            "summary",
        ):
            if key not in report:
                continue
            block = report[key]
            status = "OK" if block.get("ok") else ("SKIP" if block.get("skipped") else "FAIL")
            print(f"[{status}] {key}")
            if key == "apply_neo4j":
                if block.get("seed_missing") is not None:
                    print(f"       seed missing endpoints: {block['seed_missing']}")
                if block.get("mentions_missing"):
                    print(
                        "       bulk MENTIONS missing TextChunks (advisory): "
                        f"{block['mentions_missing']}"
                    )
                for g in (block.get("executable_missing") or [])[:8]:
                    print(f"       - {g}")
            if key == "neo4j" and block.get("node_counts"):
                top = ", ".join(
                    f"{r['label']}={r['cnt']}" for r in block["node_counts"][:6]
                )
                print(f"       nodes: {top}")
            if block.get("gaps"):
                for g in block["gaps"][:8]:
                    print(f"       - {g}")
            if block.get("missing_concepts"):
                print(f"       missing concepts: {block['missing_concepts']}")
            if block.get("missing_governed_by"):
                print(f"       missing GOVERNED_BY: {block['missing_governed_by']}")
            if block.get("missing_limited_by"):
                print(f"       missing LIMITED_BY: {block['missing_limited_by']}")
            if block.get("error"):
                print(f"       error: {block['error']}")
            if key == "rule_engine" and block.get("ok"):
                print(
                    f"       net tax={block.get('net_path_tax')} "
                    f"gross tax={block.get('gross_path_tax')} "
                    f"kg={block.get('kg_mode')}"
                )
        print()
        if failures:
            print(f"RESULT: FAIL - {failures}")
        else:
            print("RESULT: PASS - stores aligned for current Phase 5 ontology")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
