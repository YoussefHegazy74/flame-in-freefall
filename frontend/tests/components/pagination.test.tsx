import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Pagination } from "@/components/ui/pagination";

describe("Pagination", () => {
  it("shows the current row range and page count", () => {
    render(
      <Pagination total={120} limit={25} offset={25} onPageChange={() => {}} label="rows" />,
    );

    expect(screen.getByText(/Showing/)).toHaveTextContent("Showing 26–50 of 120 rows");
    expect(screen.getByText("2 / 5")).toBeInTheDocument();
  });

  it("disables previous on the first page and next on the last page", () => {
    const { rerender } = render(
      <Pagination total={10} limit={25} offset={0} onPageChange={() => {}} />,
    );

    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();

    rerender(
      <Pagination total={10} limit={5} offset={5} onPageChange={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "Previous page" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("requests the next and previous offsets", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();

    render(
      <Pagination total={100} limit={25} offset={25} onPageChange={onPageChange} />,
    );

    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPageChange).toHaveBeenLastCalledWith(50);

    await user.click(screen.getByRole("button", { name: "Previous page" }));
    expect(onPageChange).toHaveBeenLastCalledWith(0);
  });
});
