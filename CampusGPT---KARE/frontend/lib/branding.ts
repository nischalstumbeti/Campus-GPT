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
  app_name: string;
  updated_at?: string | null;
  updated_by?: string | null;
};

export const DEFAULT_BRANDING: Branding = {
  primary: "#7C5AED",
  primary_dark: "#6B4DD4",
  secondary: "#5B3AD4",
  accent: "#F59E0B",
  bg_light: "#FFFFFF",
  bg_card: "#FFFFFF",
  text_color: "#1a1a2e",
  font_family: "Tahoma, Geneva, Verdana, sans-serif",
  font_size_base: "16px",
  heading_scale: "1.25",
  background_image_url: "",
  background_overlay: "0.88",
  login_background_url: "",
  app_name: "Campus-GPT",
};

export function applyBrandingToDocument(b: Branding) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.style.setProperty("--primary", b.primary);
  root.style.setProperty("--primary-dark", b.primary_dark);
  root.style.setProperty("--secondary", b.secondary);
  root.style.setProperty("--accent", b.accent);
  root.style.setProperty("--bg-light", b.bg_light);
  root.style.setProperty("--bg-card", b.bg_card);
  root.style.setProperty("--text-color", b.text_color);
  root.style.setProperty("--font-family", b.font_family);
  root.style.setProperty("--font-size-base", b.font_size_base);
  root.style.setProperty("--heading-scale", b.heading_scale);
  root.style.setProperty("--bg-overlay", b.background_overlay || "0.88");
  root.style.setProperty(
    "--bg-image",
    b.background_image_url ? `url("${b.background_image_url.replace(/"/g, '\\"')}")` : "none"
  );
  root.style.setProperty(
    "--login-bg-image",
    b.login_background_url ? `url("${b.login_background_url.replace(/"/g, '\\"')}")` : "none"
  );

  document.body.style.fontFamily = b.font_family;
  document.body.style.fontSize = b.font_size_base;
  document.body.style.color = b.text_color;
  document.body.style.backgroundColor = b.bg_light;
}
