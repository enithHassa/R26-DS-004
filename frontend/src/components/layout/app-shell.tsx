import { NavLink, Outlet } from "react-router-dom";
import { Wallet } from "lucide-react";

import { features } from "@/features";
import { cn } from "@/lib/utils";

export function AppShell() {
  return (
    <div className="flex h-full">
      <aside className="hidden w-64 flex-col border-r bg-card/50 p-4 md:flex">
        <div className="mb-8 flex items-center gap-2 px-2">
          <Wallet className="h-6 w-6" />
          <div>
            <div className="font-semibold">AI Tax Advisory</div>
            <div className="text-xs text-muted-foreground">Decision Support</div>
          </div>
        </div>

        {features.map((feature) => (
          <div key={feature.id} className="mb-6">
            <div className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {feature.title}
            </div>
            <nav className="flex flex-col gap-1">
              {feature.nav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                    )
                  }
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
        ))}

        <div className="mt-auto px-2 text-xs text-muted-foreground">R26-DS-004</div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl p-6 md:p-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
