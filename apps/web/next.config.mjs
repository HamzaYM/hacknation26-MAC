/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Frontend calls /api/* → FastAPI on :8000 (no CORS pain in dev).
    // API_PROXY_TARGET points a second dev instance (e.g. a worktree) at
    // its own API port without touching this default.
    const target = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${target}/:path*` }];
  },
};

export default nextConfig;
