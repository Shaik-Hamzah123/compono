import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // chartjs-node-canvas's first render per test file can be slow (native
    // canvas module init) under parallel test load — the default 5s can
    // flake on a loaded machine.
    testTimeout: 15000,
  },
});
