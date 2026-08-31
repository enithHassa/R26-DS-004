import { cn } from "@/lib/utils";

import type { KgJoinFields } from "../types";
import {
  contentKindLabel,
  instrumentLabel,
  sourceSubtitle,
  sourceTitle,
  tierLabel,
} from "./language-model-display";

function isPresent(v: string | null | undefined): v is string {
  return v != null && String(v).trim().length > 0;
}

function MetaBadge({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-border/80 bg-muted/50 px-2.5 py-0.5 text-xs font-medium text-foreground/90",
        className,
      )}
    >
      {children}
    </span>
  );
}

interface LawSourceMetaProps {
  fields: KgJoinFields;
  fallbackId?: string;
  compact?: boolean;
}

export function LawSourceMeta({ fields, fallbackId, compact = false }: LawSourceMetaProps) {
  const title = sourceTitle(fields, fallbackId);
  const subtitle = sourceSubtitle(fields);
  const tier = tierLabel(fields.tier);
  const instrument = instrumentLabel(fields.instrument_type);
  const contentKind = contentKindLabel(fields.content_kind);

  const technicalRows: [string, string][] = [];
  if (isPresent(fields.source_doc_id)) {
    technicalRows.push(["Source document ID", fields.source_doc_id]);
  }
  if (isPresent(fields.section_uid)) {
    technicalRows.push(["Section UID", fields.section_uid]);
  }
  if (isPresent(fields.section_label)) {
    technicalRows.push(["Section label", fields.section_label]);
  }
  if (isPresent(fields.tier)) {
    technicalRows.push(["Authority tier", fields.tier]);
  }
  if (isPresent(fields.instrument_type)) {
    technicalRows.push(["Instrument type", fields.instrument_type]);
  }
  if (isPresent(fields.content_kind)) {
    technicalRows.push(["Content kind", fields.content_kind]);
  }

  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      <div className="space-y-1">
        <p className="text-base font-semibold leading-snug text-foreground">{title}</p>
        {subtitle && subtitle !== title ? (
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>

    </div>
  );
}
