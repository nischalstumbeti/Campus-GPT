import type { Metadata } from "next";
import InternetBanner from "@/components/InternetBanner";
import ThemeProvider from "@/components/ThemeProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Campus-GPT | Kalasalingam Academy of Research and Education",
  description: "Multi-purpose campus assistant for KARE — timetable, attendance, marks, faculty availability, academic planning, admissions, and more.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased font-sans app-themed-bg">
        <ThemeProvider>
          <InternetBanner />
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
