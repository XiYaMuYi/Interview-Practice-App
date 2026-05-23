/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, { dev, isServer }) => {
    if (dev && isServer) {
      // Disable webpack filesystem cache on Windows to prevent
      // "Cannot find module './NNN.js'" corruption errors
      config.cache = false;
    }
    return config;
  },
  async rewrites() {
    return [
      // Note: /api/v1/ai/* is handled by app/api/v1/ai/[...path]/route.ts
      // We exclude it from rewrites because the dev server proxy times out on long LLM calls (~40s)
      // Use a separate rewrite for non-AI paths
      {
        source: "/api/v1/questions/:path*",
        destination: "http://localhost:8000/api/v1/questions/:path*",
      },
      // /api/v1/resumes/* is partially handled by src/app/api/v1/resumes/[...path]/route.ts
      // (rewrites buffer SSE, so we use an explicit API route for streaming POST requests).
      // GET/DELETE sub-paths use the rewrite below; the base path also needs a rewrite.
      {
        source: "/api/v1/resumes",
        destination: "http://localhost:8000/api/v1/resumes",
      },
      {
        source: "/api/v1/resumes/:path*",
        destination: "http://localhost:8000/api/v1/resumes/:path*",
      },
      {
        source: "/api/v1/study/:path*",
        destination: "http://localhost:8000/api/v1/study/:path*",
      },
      {
        source: "/api/v1/knowledge/:path*",
        destination: "http://localhost:8000/api/v1/knowledge/:path*",
      },
      {
        source: "/api/v1/import/:path*",
        destination: "http://localhost:8000/api/v1/import/:path*",
      },
      {
        source: "/api/v1/health",
        destination: "http://localhost:8000/api/v1/health",
      },
      {
        source: "/api/v1/tasks/:path*",
        destination: "http://localhost:8000/api/v1/tasks/:path*",
      },
    ];
  },
};

export default nextConfig;
