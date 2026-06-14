import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  height?: number;
};

export function ChartCard({ title, description, children, className, height = 280 }: Props) {
  return (
    <Card className={cn("border-slate-200/80 shadow-sm", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-[var(--revenue-slate)]">{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        <div style={{ height }} className="w-full min-h-[200px]">
          {children}
        </div>
      </CardContent>
    </Card>
  );
}
