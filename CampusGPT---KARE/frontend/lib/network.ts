export const INTERNET_ISSUE_MESSAGE = "Internet issue. Check your connection and try again.";
export const INTERNET_EVENT = "campusgpt-internet-issue";
export const INTERNET_OK_EVENT = "campusgpt-internet-ok";

export class InternetIssueError extends Error {
  constructor(message = INTERNET_ISSUE_MESSAGE) {
    super(message);
    this.name = "InternetIssueError";
  }
}

export function isOffline(): boolean {
  return typeof navigator !== "undefined" && navigator.onLine === false;
}

export function isInternetIssue(err: unknown): boolean {
  if (isOffline()) return true;
  return err instanceof InternetIssueError;
}

export function notifyInternetIssue() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(INTERNET_EVENT));
}

export function userFacingError(err: unknown, fallback = "Something went wrong"): string {
  if (isOffline()) {
    notifyInternetIssue();
    return INTERNET_ISSUE_MESSAGE;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export function notifyInternetOk() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(INTERNET_OK_EVENT));
}

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    notifyInternetIssue();
    throw new InternetIssueError();
  }
  try {
    const res = await fetch(input, init);
    notifyInternetOk();
    return res;
  } catch (err) {
    if (isOffline()) {
      notifyInternetIssue();
      throw new InternetIssueError();
    }
    const message = err instanceof Error ? err.message : "";
    if (!message || message === "Failed to fetch" || message === "Load failed" || message === "NetworkError when attempting to fetch resource.") {
      throw new Error("The Campus-GPT API did not respond.");
    }
    throw err instanceof Error ? err : new Error(message);
  }
}
