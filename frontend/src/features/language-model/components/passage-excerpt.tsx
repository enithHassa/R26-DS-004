import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function splitParagraphs(text: string): string[] {
  return text
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
}

interface PassageExcerptProps {
  text: string;
  label?: string;
}

export function PassageExcerpt({ text, label = "Relevant passage" }: PassageExcerptProps) {
  const [expanded, setExpanded] = useState(false);
  const paragraphs = splitParagraphs(text);
  const longPassage = text.length > 700 || paragraphs.length > 3;

  return (
    <div className="rounded-lg border border-border/70 bg-muted/15 p-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div
        className={cn(
          "space-y-3 text-sm leading-relaxed text-foreground",
          !expanded && longPassage ? "max-h-56 overflow-hidden" : "",
        )}
      >
        {paragraphs.map((paragraph, index) => (
          <p key={`${index}-${paragraph.slice(0, 24)}`}>{paragraph}</p>
        ))}
      </div>
      {longPassage ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-3 h-8 px-2 text-xs"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Show less" : "Show full passage"}
        </Button>
      ) : null}
    </div>
  );
}
