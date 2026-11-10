import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

// jsdom does not implement matchMedia; Recharts and responsive shells use it.
// Use a plain function, not vi.fn: restoreMocks would wipe a mock implementation.
function matchMediaStub(query: string): MediaQueryList {
  return {
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  } as MediaQueryList;
}

Object.defineProperty(window, "matchMedia", {
  configurable: true,
  writable: true,
  value: matchMediaStub,
});

Object.defineProperty(globalThis, "matchMedia", {
  configurable: true,
  writable: true,
  value: matchMediaStub,
});

// Recharts uses ResizeObserver in responsive containers.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(window, "ResizeObserver", {
  writable: true,
  value: ResizeObserverStub,
});

Object.defineProperty(globalThis, "ResizeObserver", {
  writable: true,
  value: ResizeObserverStub,
});

// Give Recharts a non-zero size in jsdom.
Object.defineProperty(HTMLElement.prototype, "getBoundingClientRect", {
  configurable: true,
  value: function getBoundingClientRect() {
    return {
      width: 900,
      height: 360,
      top: 0,
      left: 0,
      bottom: 360,
      right: 900,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    };
  },
});
