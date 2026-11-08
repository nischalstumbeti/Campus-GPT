"use client";

/** Impressive cloud background – clouds positioned to avoid overlap, task-based intensity. */
export type CloudVariant = "hero" | "form" | "chat" | "admin";

export default function CloudBackground({ variant = "form" }: { variant?: CloudVariant }) {
  // Variant controls opacity: hero = most visible, admin = subtle
  const opacity = variant === "hero" ? 0.14 : variant === "form" ? 0.10 : variant === "chat" ? 0.08 : 0.06;

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0" aria-hidden>
      {/* Top-left - large, slow */}
      <div
        className="absolute rounded-[100px] bg-[#7C5AED] cloud-float-1"
        style={{
          top: "8%",
          left: "2%",
          width: 180,
          height: 50,
          opacity: opacity * 1.2,
          boxShadow: "60px 25px 0 -8px #7C5AED",
        }}
      />
      {/* Top-right - medium */}
      <div
        className="absolute rounded-[100px] bg-[#7C5AED] cloud-float-2"
        style={{
          top: "15%",
          right: "3%",
          width: 140,
          height: 40,
          opacity: opacity,
          boxShadow: "45px 20px 0 -10px #7C5AED",
        }}
      />
      {/* Middle-left - small */}
      <div
        className="absolute rounded-full bg-[#7C5AED] cloud-float-3"
        style={{
          top: "45%",
          left: "5%",
          width: 100,
          height: 35,
          opacity: opacity * 0.8,
        }}
      />
      {/* Middle-right - medium */}
      <div
        className="absolute rounded-[100px] bg-[#7C5AED] cloud-float-1"
        style={{
          top: "55%",
          right: "8%",
          width: 120,
          height: 38,
          opacity: opacity * 0.9,
          boxShadow: "40px 15px 0 -8px #7C5AED",
        }}
      />
      {/* Bottom-left - medium */}
      <div
        className="absolute rounded-[100px] bg-[#7C5AED] cloud-float-2"
        style={{
          bottom: "15%",
          left: "10%",
          width: 130,
          height: 42,
          opacity: opacity * 0.85,
          boxShadow: "50px 18px 0 -9px #7C5AED",
        }}
      />
      {/* Bottom-right - large, gentle drift */}
      <div
        className="absolute rounded-[120px] bg-[#7C5AED] cloud-drift"
        style={{
          bottom: "8%",
          right: "5%",
          width: 160,
          height: 45,
          opacity: opacity * 0.5,
          boxShadow: "55px 22px 0 -12px #7C5AED",
        }}
      />
      {/* Subtle pulse accent - center */}
      <div
        className="absolute rounded-full bg-[#7C5AED] cloud-pulse"
        style={{
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: 200,
          height: 60,
          opacity: opacity * 0.3,
        }}
      />
    </div>
  );
}
