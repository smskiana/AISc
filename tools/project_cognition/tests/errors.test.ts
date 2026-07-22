import assert from "node:assert/strict";
import test from "node:test";
import { CognitionError, toCognitionError } from "../src/domain/errors.js";

test("errors expose stable codes instead of free-text parsing", () => {
  assert.deepEqual(toCognitionError(new Error("SCOPE_EXPIRED")), { code: "SCOPE_EXPIRED", message: "SCOPE_EXPIRED", details: undefined });
  assert.deepEqual(toCognitionError(new CognitionError("BOUNDARY_VIOLATION", "outside", { id: "x" })), { code: "BOUNDARY_VIOLATION", message: "outside", details: { id: "x" } });
  assert.equal(toCognitionError(new Error("connection refused")).code, "ADAPTER_UNAVAILABLE");
});
