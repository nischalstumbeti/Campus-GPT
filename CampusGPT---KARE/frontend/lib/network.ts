export const INTERNET_ISSUE_MESSAGE = "Internet issue. Check your connection and try again.";
export const INTERNET_EVENT = "campusgpt-internet-issue";
export const INTERNET_OK_EVENT = "campusgpt-internet-ok";

export class InternetIssueError extends Error {
  constructor(message = INTERNET_ISSUE_MESSAGE) {
    super(message);
    this.name = "InternetIssueError";
  }
}

export function isInternetIssue(err: unknown): boolean {
  if (typeof navigator !== "undefined" && navigator.onLine === false) return true;
  if (err instanceof InternetIssueError) return true;
  const msg = err instanceof Error ? `${err.name} ${err.message}` : String(err ?? "");
  const lower = msg.toLowerCase();
  return (
    lower.includes("failed to fetch") ||
    lower.includes("networkerror") ||
    lower.includes("network request failed") ||
    lower.includes("load failed") ||
    lower.includes("err_internet") ||
    lower.includes("err_network") ||
    lower.includes("err_name_not_resolved") ||
    lower.includes("err_connection") ||
    lower.includes("net::err") ||
    lower.includes("internet issue")
  );
}

export function notifyInternetIssue() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(INTERNET_EVENT));
}

export function userFacingError(err: unknown, fallback = "Something went wrong"): string {
  if (isInternetIssue(err)) {
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
    if (isInternetIssue(err)) {
      notifyInternetIssue();
      throw new InternetIssueError();
    }
    throw err;
  }
}
