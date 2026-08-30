import { Link } from "react-router-dom";
import { ArrowRight, Library } from "lucide-react";

import { Button } from "@/components/ui/button";

export function LoadNewActPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Load new act</h2>
        <p className="text-sm text-muted-foreground">
          Protected admin upload runs quote-gated LLM extract, human review, impact preview, and
          activation. Open Act admin to upload a PDF. Past Acts holds the corpus library and
          fixture tools.
        </p>
      </div>

      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Library className="h-4 w-4" />
          </span>
          <div className="min-w-0 space-y-1">
            <p className="font-medium">Act admin upload</p>
            <p className="text-sm text-muted-foreground">
              Upload an Inland Revenue Act PDF, run extract, review quotes, then activate into year
              views when ready.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" asChild>
            <Link to="/optimization-explainable-engine/act-admin">
              Open Act admin
              <ArrowRight className="ml-1.5 h-4 w-4" />
            </Link>
          </Button>
          <Button type="button" variant="outline" asChild>
            <Link to="/optimization-explainable-engine/past-acts">Past Acts</Link>
          </Button>
        </div>
      </div>

      <Button type="button" variant="outline" asChild>
        <Link to="/optimization-explainable-engine/home">Back to home</Link>
      </Button>
    </div>
  );
}
