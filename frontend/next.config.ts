import path from "path";
import type { NextConfig } from "next";

const BACKEND_URL =
  process.env.BACKEND_URL || "http://127.0.0.1:9191";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: path.resolve(__dirname, ".."),
  },
  // Proxy all backend requests to FastAPI
  async rewrites() {
    return [
      // API endpoints
      {
        source: "/api/v1/:path*",
        destination: `${BACKEND_URL}/api/v1/:path*`,
      },
      {
        source: "/api/v2/:path*",
        destination: `${BACKEND_URL}/api/v2/:path*`,
      },
      // OAuth initiators and callbacks
      {
        source: "/google/:path*",
        destination: `${BACKEND_URL}/google/:path*`,
      },
      {
        source: "/github/:path*",
        destination: `${BACKEND_URL}/github/:path*`,
      },
      {
        source: "/azure/:path*",
        destination: `${BACKEND_URL}/azure/:path*`,
      },
      {
        source: "/oidc/:path*",
        destination: `${BACKEND_URL}/oidc/:path*`,
      },
      // SAML
      {
        source: "/saml/:path*",
        destination: `${BACKEND_URL}/saml/:path*`,
      },
      // DynDNS
      {
        source: "/nic/:path*",
        destination: `${BACKEND_URL}/nic/:path*`,
      },
      // Health check
      {
        source: "/ping",
        destination: `${BACKEND_URL}/ping`,
      },
      // Email confirmation
      {
        source: "/confirm/:path*",
        destination: `${BACKEND_URL}/confirm/:path*`,
      },
      // Swagger spec
      {
        source: "/swagger",
        destination: `${BACKEND_URL}/swagger`,
      },
    ];
  },
};

export default nextConfig;
