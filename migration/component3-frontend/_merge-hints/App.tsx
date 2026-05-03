import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { features } from "@/features";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        {features.flatMap((feature) => {
          const childRoutes = feature.routes.map((route, idx) => (
            <Route
              key={`${feature.id}-${idx}`}
              index={route.index}
              path={route.path}
              element={route.element}
            />
          ));
          if (feature.layout) {
            const Layout = feature.layout;
            return (
              <Route key={`${feature.id}-layout`} element={<Layout />}>
                {childRoutes}
              </Route>
            );
          }
          return childRoutes;
        })}
      </Route>
    </Routes>
  );
}
