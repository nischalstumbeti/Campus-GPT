function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function safeNoticeHref(value: string) {
  const raw = value.trim();
  if (!raw) return "";
  const withScheme = raw.toLowerCase().startsWith("www.") ? `https://${raw}` : raw;
  const lowered = withScheme.toLowerCase();
  if (
    lowered.startsWith("http://") ||
    lowered.startsWith("https://") ||
    lowered.startsWith("mailto:") ||
    withScheme.startsWith("/")
  ) {
    return withScheme;
  }
  return "";
}

/** Keep plain text and anchor tags only. A link applies to the words inside that anchor. */
export function sanitizeNoticeHtml(input: string) {
  const doc = new DOMParser().parseFromString(input || "", "text/html");
  const out: string[] = [];
  const walk = (node: Node) => {
    node.childNodes.forEach((child) => {
      if (child.nodeType === Node.TEXT_NODE) {
        out.push(escapeHtml(child.textContent || ""));
        return;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) return;
      const el = child as HTMLElement;
      if (el.tagName === "BR") {
        out.push(" ");
        return;
      }
      if (el.tagName === "A") {
        const href = safeNoticeHref(el.getAttribute("href") || "");
        if (href) {
          const extra = href.startsWith("/") ? "" : ' target="_blank" rel="noreferrer"';
          out.push(`<a href="${escapeHtml(href)}"${extra}>`);
          walk(el);
          out.push("</a>");
          return;
        }
      }
      walk(el);
    });
  };
  walk(doc.body);
  return out.join("").replace(/\s+/g, " ").trim();
}

export function noticeText(input: string) {
  const doc = new DOMParser().parseFromString(sanitizeNoticeHtml(input), "text/html");
  return (doc.body.textContent || "").trim();
}
