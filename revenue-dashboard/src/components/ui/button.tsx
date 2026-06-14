import * as React from "react";

import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "ghost" | "outline";
  size?: "default" | "sm" | "icon";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--revenue-teal)] disabled:pointer-events-none disabled:opacity-50",
        variant === "default" && "bg-[var(--revenue-teal)] text-white hover:bg-[#0a5252]",
        variant === "ghost" && "hover:bg-[var(--revenue-teal-light)] text-[var(--revenue-slate)]",
        variant === "outline" && "border border-[var(--color-border)] bg-white hover:bg-slate-50",
        size === "default" && "h-9 px-4 py-2",
        size === "sm" && "h-8 px-3 text-xs",
        size === "icon" && "h-9 w-9",
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
