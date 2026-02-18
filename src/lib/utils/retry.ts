/**
 * retry.ts
 *
 * 指数バックオフ付きリトライユーティリティ。
 * API 呼び出しの一時的な障害に対して自動リトライを提供する。
 */

export interface RetryOptions {
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
}

const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxAttempts: 3,
  baseDelayMs: 1000,
  maxDelayMs: 30000,
  backoffMultiplier: 2,
};

export class RetryableError extends Error {
  readonly shouldRetry: boolean;

  constructor(message: string, shouldRetry: boolean, cause?: Error) {
    super(message);
    this.name = "RetryableError";
    this.shouldRetry = shouldRetry;
    if (cause) {
      this.cause = cause;
    }
  }
}

export function isRetryableError(error: unknown): boolean {
  if (error instanceof RetryableError) {
    return error.shouldRetry;
  }

  if (!(error instanceof Error)) {
    return false;
  }

  const message = error.message.toLowerCase();

  if (
    message.includes("network") ||
    message.includes("econnreset") ||
    message.includes("econnrefused") ||
    message.includes("enotfound") ||
    message.includes("fetch failed") ||
    message.includes("socket hang up")
  ) {
    return true;
  }

  if (
    message.includes("rate limit") ||
    message.includes("429") ||
    message.includes("too many requests") ||
    message.includes("quota")
  ) {
    return true;
  }

  if (
    message.includes("timeout") ||
    message.includes("etimedout") ||
    message.includes("deadline exceeded")
  ) {
    return true;
  }

  if (
    message.includes("500") ||
    message.includes("502") ||
    message.includes("503") ||
    message.includes("504") ||
    message.includes("internal server error") ||
    message.includes("bad gateway") ||
    message.includes("service unavailable") ||
    message.includes("gateway timeout")
  ) {
    return true;
  }

  if ("status" in error && typeof (error as { status: unknown }).status === "number") {
    const status = (error as { status: number }).status;
    if (status === 429 || (status >= 500 && status < 600)) {
      return true;
    }
  }

  return false;
}

function calculateDelay(attempt: number, options: RetryOptions): number {
  const delay = options.baseDelayMs * Math.pow(options.backoffMultiplier, attempt);
  const jitter = delay * 0.1 * Math.random();
  return Math.min(delay + jitter, options.maxDelayMs);
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }

    const timer = setTimeout(resolve, ms);

    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true }
    );
  });
}

export async function withRetry<T>(
  operation: () => Promise<T>,
  options?: Partial<RetryOptions>,
  signal?: AbortSignal
): Promise<T> {
  const opts: RetryOptions = { ...DEFAULT_RETRY_OPTIONS, ...options };
  let lastError: unknown;

  for (let attempt = 0; attempt < opts.maxAttempts; attempt++) {
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    try {
      return await operation();
    } catch (error) {
      lastError = error;

      const isLastAttempt = attempt === opts.maxAttempts - 1;
      if (isLastAttempt || !isRetryableError(error)) {
        throw error;
      }

      const delay = calculateDelay(attempt, opts);
      await sleep(delay, signal);
    }
  }

  throw lastError;
}
