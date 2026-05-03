import type { ComponentType } from "react";
import type { RouteObject } from "react-router-dom";

/** Optional layout (Outlet) wrapping all routes for this feature — used for module-scoped theming. */
export type FeatureLayout = ComponentType;

export interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
}

/**
 * Each research component (1..4) exports a FeatureModule from its
 * `src/features/<component>/index.ts` so the shared shell can compose
 * the final app without knowing about individual components.
 */
export interface FeatureModule {
  id: string;
  title: string;
  routes: RouteObject[];
  nav: NavItem[];
  /** When set, routes render inside this layout (e.g. scoped CSS variables for the module). */
  layout?: FeatureLayout;
}
