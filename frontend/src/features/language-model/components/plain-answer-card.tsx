import { Sparkles } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface PlainAnswerCardProps {
  answer: string;
  provider?: string | null;
  model?: string | null;
}

export function PlainAnswerCard({
  answer,
  provider,
  model,
}: PlainAnswerCardProps) {
  const paragraphs = answer
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);

  return (
    <Card className="overflow-hidden rounded-xl border border-emerald-200/80 bg-emerald-50/40 shadow-sm dark:border-emerald-900/50 dark:bg-emerald-950/20">
      <div className="h-1 w-full bg-gradient-to-r from-emerald-600/80 to-primary/70" aria-hidden />
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Sparkles className="h-5 w-5 text-emerald-700 dark:text-emerald-300" />
          Plain-language answer
        </CardTitle>
        <CardDescription>
          A short summary based on the retrieved passages and any linked knowledge-graph notes.
          {provider || model ? (
            <>
              {" "}
              Generated with {provider ?? "an LLM"}
              {model ? ` (${model})` : ""}.
            </>
          ) : null}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-3 text-sm leading-relaxed text-foreground">
          {paragraphs.map((paragraph, index) => (
            <p key={`${index}-${paragraph.slice(0, 24)}`}>{paragraph}</p>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          This is decision support, not legal advice. Check the source excerpts and related tax
          knowledge below before relying on it.
        </p>
      </CardContent>
    </Card>
  );
}

export function PlainAnswerUnavailable({ requested }: { requested: boolean }) {
  if (!requested) return null;

  return (
    <Card className="rounded-xl border border-dashed border-border/80 bg-muted/10 shadow-sm">
      <CardContent className="space-y-2 p-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">Plain-language answer not available</p>
        <p>
          Turn on answer synthesis on the server and set a Gemini API key, then run the query again
          with the summary option enabled.
        </p>
      </CardContent>
    </Card>
  );
}
