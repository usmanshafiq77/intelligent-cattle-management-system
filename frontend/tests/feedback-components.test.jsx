import { act, fireEvent, render } from "@testing-library/react-native";

import { ConfirmationDialog } from "../src/components/ui/ConfirmationDialog";
import { FeedbackState } from "../src/components/ui/FeedbackState";
import { StatusBadge } from "../src/components/ui/StatusBadge";
import { ThemeProvider } from "../src/theme/ThemeProvider";

jest.mock("../src/theme/useAppReducedMotion", () => ({ useAppReducedMotion: () => true }));

async function renderThemed(component) {
  return render(<ThemeProvider persistPreference={false}>{component}</ThemeProvider>);
}

describe("feedback components", () => {
  test("status badges provide a screen-reader status label", async () => {
    const screen = await renderThemed(<StatusBadge status="warning" label="Vaccination due" />);
    expect(screen.getByLabelText("Status: Vaccination due")).toBeTruthy();
  });

  test("error state exposes retry only when a callback is provided", async () => {
    const onRetry = jest.fn();
    const screen = await renderThemed(<FeedbackState type="error" actionLabel="Retry" onAction={onRetry} />);
    fireEvent.press(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  test("confirmation dialog calls explicit cancel and confirm actions", async () => {
    jest.useFakeTimers();
    const onCancel = jest.fn();
    const onConfirm = jest.fn();
    const screen = await renderThemed(
      <ConfirmationDialog visible title="Confirm test" message="No data will change." onCancel={onCancel} onConfirm={onConfirm} />,
    );

    await act(async () => {
      jest.runOnlyPendingTimers();
    });

    fireEvent.press(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.press(screen.getByRole("button", { name: "Confirm" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledTimes(1);
    jest.useRealTimers();
  });
});
