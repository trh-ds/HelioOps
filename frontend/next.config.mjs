/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['three'],
  output: 'standalone',

  // Development API proxy to backend
  // In production, configure your reverse proxy (nginx, Caddy, etc.)
  async rewrites() {
    return {
      beforeFiles: [
        { source: '/api/:path*', destination: 'http://localhost:8000/api/:path*' },
        { source: '/health/:path*', destination: 'http://localhost:8000/health/:path*' },
        { source: '/metrics', destination: 'http://localhost:8000/metrics' },
        // WebSocket proxy — requires custom middleware in production
        { source: '/ws/:path*', destination: 'http://localhost:8000/ws/:path*' },
      ],
    }
  },
}

export default nextConfig

