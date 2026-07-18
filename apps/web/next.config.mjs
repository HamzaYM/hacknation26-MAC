/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Frontend calls /api/* → FastAPI on :8000 (no CORS pain in dev)
    return [{ source: "/api/:path*", destination: "http://localhost:8000/:path*" }];
  },
};

export default nextConfig;
