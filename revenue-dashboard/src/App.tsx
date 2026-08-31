import { RevenueDashboardPage } from "./pages/dashboard";

export default function App() {
  return (
    <div className="min-h-screen" data-revenue-analytics>
      <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8 md:py-10">
        <RevenueDashboardPage />
      </div>
    </div>
  );
}
