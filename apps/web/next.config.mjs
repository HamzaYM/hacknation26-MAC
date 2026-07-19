/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Frontend calls /api/* → FastAPI (no CORS pain in dev). Defaults to :8000;
    // override with API_PROXY_TARGET to point a worktree dev server at its own API.
    const target = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${target}/:path*` }];
  },
};

export default nextConfig;
