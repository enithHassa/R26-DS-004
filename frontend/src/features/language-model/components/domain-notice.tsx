import { ShieldAlert } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface DomainNoticeProps {
  status?: string | null;
  message?: string | null;
}

export function DomainNotice({ status, message }: DomainNoticeProps) {
  if (!status || status === "in_domain" || !message) {
    return null;
  }

  const title = status === "off_topic" ? "Outside tax scope" : "No strong legal match";

  return (
    <Card className="rounded-xl border border-amber-300/80 bg-amber-50/70 shadow-sm dark:border-amber-900/60 dark:bg-amber-950/20">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg text-amber-950 dark:text-amber-100">
          <ShieldAlert className="h-5 w-5" />
          {title}
        </CardTitle>
        <CardDescription className="text-amber-900/90 dark:text-amber-200/90">
          {message}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0 text-sm text-amber-900/90 dark:text-amber-100/90">
        Ask about Sri Lankan income tax topics such as personal relief, residency, deductions, or
        filing deadlines.
      </CardContent>
    </Card>
  );
}
