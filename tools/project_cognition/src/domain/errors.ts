export interface CognitionErrorBody {
  code: string;
  message: string;
  details?: unknown;
}

export class CognitionError extends Error {
  /** Creates a stable, machine-readable domain error. */
  public constructor(public readonly code: string, message = code, public readonly details?: unknown) {
    super(message);
    this.name = "CognitionError";
  }
}

/** Normalizes internal and adapter failures into the public error contract. */
export function toCognitionError(error: unknown): CognitionErrorBody {
  if (error instanceof CognitionError) return { code: error.code, message: error.message, details: error.details };
  const message = error instanceof Error ? error.message : String(error);
  const stableCode = /^[A-Z][A-Z0-9_]+$/.test(message) ? message : "ADAPTER_UNAVAILABLE";
  return { code: stableCode, message, details: stableCode === "ADAPTER_UNAVAILABLE" ? { cause: message } : undefined };
}
