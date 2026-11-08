export type Branding = {
  id?: number | null;
  primary: string;
  primary_dark: string;
  secondary: string;
  accent: string;
  bg_light: string;
  bg_card: string;
  text_color: string;
  font_family: string;
  font_size_base: string;
  heading_scale: string;
  background_image_url: string;
  background_overlay: string;
  login_background_url: string;
  logo_url: string;
  header_title: string;
  header_subtitle: string;
  footer_text: string;
  sign_in_label: string;
  app_name: string;
};

export const DEFAULT_BRANDING: Branding = {
  primary: "#0B2A4A",
  primary_dark: "#071E36",
  secondary: "#1E4A7A",
  accent: "#C9A227",
  bg_light: "#F4F7FB",
  bg_card: "#FFFFFF",
  text_color: "#0F172A",
  font_family: "Verdana, Tahoma, sans-serif",
  font_size_base: "16px",
  heading_scale: "1.25",
  background_image_url: "",
  background_overlay: "0.9",
  login_background_url: "",
  logo_url: "",
  header_title: "",
  header_subtitle: "",
  footer_text: "",
  sign_in_label: "",
  app_name: "",
};

function cssColor(value: string | undefined, fallback: string) {
  return value && /^#[0-9a-fA-F]{3,8}$/.test(value.trim()) ? value.trim() : fallback;
}

function cssFont(value: string | undefined, fallback: string) {
  const clean = (value || "").replace(/[{};<>]/g, "").trim();
  return clean || fallback;
}

export function applyBrandingToDocument(b: Branding) {
  if (typeof document === "undefined") return;
  const primary = cssColor(b.primary, DEFAULT_BRANDING.primary);
  const primaryDark = cssColor(b.primary_dark, DEFAULT_BRANDING.primary_dark);
  const secondary = cssColor(b.secondary, DEFAULT_BRANDING.secondary);
  const accent = cssColor(b.accent, DEFAULT_BRANDING.accent);
  const panel = cssColor(b.bg_light, DEFAULT_BRANDING.bg_light);
  const ink = cssColor(b.text_color, DEFAULT_BRANDING.text_color);
  const font = cssFont(b.font_family, DEFAULT_BRANDING.font_family);
  const root = document.documentElement;
  root.style.setProperty("--brand", primary);
  root.style.setProperty("--brand-dark", primaryDark);
  root.style.setProperty("--accent", secondary);
  root.style.setProperty("--gold", accent);
  root.style.setProperty("--panel", panel);
  root.style.setProperty("--ink", ink);
  root.style.setProperty("--font-family", font);
  root.style.setProperty("--font-size-base", b.font_size_base || DEFAULT_BRANDING.font_size_base);
  root.style.setProperty("--heading-scale", b.heading_scale || DEFAULT_BRANDING.heading_scale);
  root.style.setProperty("--bg-overlay", b.background_overlay || "0.9");
  const image = (b.background_image_url || "").trim();
  const safeImage = /^(https?:|data:image\/|\/)/.test(image) ? image.replace(/["\\\n\r]/g, "") : "";
  root.style.setProperty("--bg-image", safeImage ? `url("${safeImage}")` : "none");
  document.body.style.fontFamily = font;
  document.body.style.fontSize = b.font_size_base || DEFAULT_BRANDING.font_size_base;
  document.body.style.color = ink;
  document.body.style.backgroundColor = panel;

  // Pages still use the original navy/gold utilities. Remap those so CMS colors show everywhere.
  let style = document.getElementById("uis-brand-overrides") as HTMLStyleElement | null;
  if (!style) {
    style = document.createElement("style");
    style.id = "uis-brand-overrides";
    document.head.appendChild(style);
  }
  style.textContent = `
    .text-\\[\\#0B2A4A\\], .text-\\[\\#0b2a4a\\] { color: ${primary} !important; }
    .bg-\\[\\#0B2A4A\\], .bg-\\[\\#0b2a4a\\], .hover\\:bg-\\[\\#163A5C\\]:hover { background-color: ${primary} !important; }
    .border-\\[\\#0B2A4A\\], .border-\\[\\#0b2a4a\\] { border-color: ${primary} !important; }
    .bg-\\[\\#1A4A7A\\], .bg-\\[\\#1a4a7a\\] { background-color: ${secondary} !important; }
    .text-\\[\\#F5C542\\], .text-\\[\\#f5c542\\] { color: ${accent} !important; }
    .bg-\\[\\#F4F6F9\\], .bg-\\[\\#f4f6f9\\], .bg-\\[\\#F4F7FB\\] { background-color: ${panel} !important; }
  `;
}

export function notifyBrandingChanged() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event("uis-branding-updated"));
}

export function notifyMarqueeChanged() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event("uis-marquee-updated"));
}
