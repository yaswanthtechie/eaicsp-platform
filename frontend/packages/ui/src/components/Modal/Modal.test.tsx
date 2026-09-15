
import { describe, it, expect } from "vitest";
import {
  render,
  screen,
  fireEvent,
} from "@testing-library/react";
import { Modal } from "./Modal";

describe("Modal accessibility", () => {
  it("traps Tab focus from the last element to the close button", () => {
    render(
      <Modal
        isOpen={true}
        title="Test Modal"
        onClose={() => {}}
      >
        <button type="button">First action</button>
        <button type="button">Last action</button>
      </Modal>
    );

    const lastButton = screen.getByRole("button", {
      name: "Last action",
    });

    const closeButton = screen.getByRole("button", {
      name: "Close modal",
    });

    lastButton.focus();

    fireEvent.keyDown(window, {
      key: "Tab",
    });

    expect(closeButton).toHaveFocus();
  });

  it("traps Shift+Tab focus from the close button to the last element", () => {
    render(
      <Modal
        isOpen={true}
        title="Test Modal"
        onClose={() => {}}
      >
        <button type="button">First action</button>
        <button type="button">Last action</button>
      </Modal>
    );

    const lastButton = screen.getByRole("button", {
      name: "Last action",
    });

    const closeButton = screen.getByRole("button", {
      name: "Close modal",
    });

    closeButton.focus();

    fireEvent.keyDown(window, {
      key: "Tab",
      shiftKey: true,
    });

    expect(lastButton).toHaveFocus();
  });
});
