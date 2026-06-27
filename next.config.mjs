/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    if (!process.env.LOCAL_API_PORT) {
      return [];
    }

    return [
      {
        source: "/api/analyze",
        destination: `http://127.0.0.1:${process.env.LOCAL_API_PORT}/api/analyze`
      }
    ];
  }
};

export default nextConfig;
