import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { InterviewIncomePage } from "./pages/income";
import { InterviewProvider } from "./session";
import { TerminalBenefitSection } from "./terminal-benefit-section";
import { SESSION_STORAGE_KEY, createDefaultSession } from "./types";

function seedSession(year = "2025_26"): void {
  const session = createDefaultSession();
  session.assessmentYear = year;
  sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

function renderSection(year = "2025_26") {
  seedSession(year);
  return render(
    <InterviewProvider>
      <TerminalBenefitSection
        open
        onToggle={() => undefined}
        actVersionLabel="IRA Act 24/2017"
        onExplain={() => undefined}
      />
    </InterviewProvider>,
  );
}

function terminalCard() {
  return screen.getByRole("button", { name: /Retirement & terminal benefits/i }).closest(
    "div.space-y-3",
  ) as HTMLElement;
}

function yesRadio() {
  return within(terminalCard()).getByRole("radio", { name: "Yes" });
}

function noRadio() {
  return within(terminalCard()).getByRole("radio", { name: "No" });
}

async function expandTerminalOnIncomePage(
  user: ReturnType<typeof userEvent.setup>,
): Promise<void> {
  await user.click(screen.getByRole("button", { name: /Retirement & terminal benefits/i }));
}

function renderIncomePage(year = "2025_26") {
  seedSession(year);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <InterviewProvider>
          <InterviewIncomePage />
        </InterviewProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TerminalBenefitSection", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("defaults to No and uses the shared catalog card shell", () => {
    renderSection();
    expect(
      screen.getByRole("button", { name: /Retirement & terminal benefits/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/special ladder/i)).toBeInTheDocument();
    expect(noRadio()).toBeChecked();
    expect(screen.queryByLabelText("Type")).not.toBeInTheDocument();
    expect(screen.queryByText("Qualifying terminal benefits")).not.toBeInTheDocument();
  });

  it("shows a row on Yes, add/remove, and unique types", async () => {
    const user = userEvent.setup();
    renderSection();
    await user.click(yesRadio());
    expect(screen.getByLabelText("Type")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Type"), "retiring_gratuity");
    await user.click(screen.getByRole("button", { name: "+ Add another terminal benefit" }));

    const typeSelects = screen.getAllByLabelText("Type");
    expect(typeSelects).toHaveLength(2);
    expect(
      within(typeSelects[1] as HTMLElement).queryByRole("option", { name: "Retiring gratuity" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove Retiring gratuity" }));
    expect(screen.getAllByLabelText("Type")).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: /Remove/ }));
    expect(noRadio()).toBeChecked();
    expect(screen.queryByLabelText("Type")).not.toBeInTheDocument();
  });

  it("hides the >20-year question on 2025/26", async () => {
    const user = userEvent.setup();
    renderSection("2025_26");
    await user.click(yesRadio());
    expect(screen.queryByText("More than 20 years")).not.toBeInTheDocument();
    expect(screen.queryByText(/When was this paid in 2019\/20/)).not.toBeInTheDocument();
  });

  it("shows the 2019/20 period radios and requires them", async () => {
    const user = userEvent.setup();
    renderSection("2019_20");
    await user.click(yesRadio());
    expect(screen.getByText(/When was this paid in 2019\/20/)).toBeInTheDocument();
    await user.click(screen.getByLabelText("1 April 2019 – 31 December 2019"));
    expect(screen.getByText("More than 20 years")).toBeInTheDocument();
  });

  it("shows the Commissioner-General checkbox only for loss of office", async () => {
    const user = userEvent.setup();
    renderSection();
    await user.click(yesRadio());
    await user.selectOptions(screen.getByLabelText("Type"), "commuted_pension");
    expect(
      screen.queryByText(/scheme uniformly applicable to all employees/),
    ).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Type"), "loss_of_office_compensation");
    expect(screen.getByText(/scheme uniformly applicable to all employees/)).toBeInTheDocument();
  });

  it("blocks Continue to reliefs when Yes and a row is incomplete", async () => {
    const user = userEvent.setup();
    renderIncomePage();
    expect(screen.getByRole("button", { name: "Continue to reliefs" })).toBeEnabled();
    await expandTerminalOnIncomePage(user);
    await user.click(screen.getByRole("radio", { name: "Yes" }));
    expect(screen.getByRole("button", { name: "Continue to reliefs" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(/Complete each retirement/);
  });
});
