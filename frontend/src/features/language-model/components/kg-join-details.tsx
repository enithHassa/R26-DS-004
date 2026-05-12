import type { KgJoinFields } from "../types";

function isPresent(v: string | null | undefined): v is string {
  return v != null && String(v).trim().length > 0;
}

/** Phase 3 Step 15 — compact graph join metadata when the corpus row provides it. */
export function KgJoinDetails({ fields }: { fields: KgJoinFields }) {
  const rows: [string, string][] = [];
  if (isPresent(fields.source_doc_id)) {
    rows.push(["Source doc", fields.source_doc_id]);
  }
  if (isPresent(fields.section_uid)) {
    rows.push(["Section UID", fields.section_uid]);
  }
  if (isPresent(fields.section_label)) {
    rows.push(["Section label", fields.section_label]);
  }
  if (isPresent(fields.tier)) {
    rows.push(["Tier", fields.tier]);
  }
  if (isPresent(fields.instrument_type)) {
    rows.push(["Instrument", fields.instrument_type]);
  }
  if (isPresent(fields.content_kind)) {
    rows.push(["Content", fields.content_kind]);
  }
  if (rows.length === 0) {
    return null;
  }
  return (
    <dl className="mt-2 grid gap-x-4 gap-y-1 border-t border-border/60 pt-2 text-xs text-muted-foreground sm:grid-cols-2">
      {rows.map(([k, v]) => (
        <div key={k} className="min-w-0 sm:contents">
          <dt className="font-medium text-foreground/80">{k}</dt>
          <dd className="break-all font-mono text-[11px] text-foreground/90">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
