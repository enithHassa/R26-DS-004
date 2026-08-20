import type { KnowledgeVersions } from "../api";

type CalculatedUsingStripProps = {
  versions: KnowledgeVersions | null | undefined;
  /** Pin below page header on report view */
  sticky?: boolean;
  className?: string;
};

function formatRulePack(value: string | undefined): string | undefined {
  if (!value) return undefined;
  return value.replace(/_/g, "/").replace(".current", " (current)");
}

export function CalculatedUsingStrip({
  versions,
  sticky = false,
  className = "",
}: CalculatedUsingStripProps) {
  if (!versions) return null;

  const rows: Array<{ label: string; value: string }> = [];
  const act = versions.act_version_label || versions.act_version;
  if (act) rows.push({ label: "Act", value: act });
  if (versions.catalog_version) {
    rows.push({ label: "Catalog", value: versions.catalog_version });
  }
  const rulePack = formatRulePack(versions.rule_pack_version);
  if (rulePack) rows.push({ label: "Rule pack", value: rulePack });
  if (versions.knowledge_graph_version) {
    rows.push({ label: "Knowledge graph", value: versions.knowledge_graph_version });
  }
  if (versions.extraction_version) {
    rows.push({ label: "Extraction", value: versions.extraction_version });
  }

  if (rows.length === 0) return null;

  return (
    <div
      className={[
        "rounded-lg border border-border/80 bg-muted/40 px-3 py-2.5 text-xs shadow-sm",
        sticky ? "sticky top-0 z-10 backdrop-blur supports-[backdrop-filter]:bg-muted/70" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label="Calculated using knowledge sources"
    >
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Calculated using
      </p>
      <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-5">
        {rows.map((row) => (
          <div key={row.label} className="min-w-0">
            <dt className="text-[10px] text-muted-foreground">{row.label}</dt>
            <dd className="truncate font-medium text-foreground" title={row.value}>
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
