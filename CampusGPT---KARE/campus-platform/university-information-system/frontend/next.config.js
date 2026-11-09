/** @type {import('next').NextConfig} */
const backend = (process.env.NEXT_PUBLIC_UIS_API_URL || "https://cims-api-g0rm.onrender.com").replace(/\/$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
