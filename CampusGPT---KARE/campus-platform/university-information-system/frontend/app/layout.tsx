import type { Metadata } from "next";
import ThemeProvider from "@/components/ThemeProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "University Information System",
  description: "Institutional information system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="app-themed-bg">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
