/**
 * Cloudflare Worker for Open3Words
 * Lightweight edge deployment — encode/decode only (no AI, no voice).
 *
 * Deploy:
 *   wrangler publish
 *
 * This is a minimal stateless implementation for low-latency global access.
 * The full API (voice, AI, blockchain) should run on a traditional server.
 */

// Embedded mini wordlist (first 100 words for demo — in production, load full list)
// In a real deployment, use KV Store to hold the 40K word list.
const DEMO_MODE = true;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS headers
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // Route handling
    if (url.pathname === "/health") {
      return jsonResponse({ status: "healthy", runtime: "cloudflare-worker" }, corsHeaders);
    }

    if (url.pathname === "/encode" && request.method === "GET") {
      const lat = parseFloat(url.searchParams.get("lat"));
      const lon = parseFloat(url.searchParams.get("lon"));

      if (isNaN(lat) || isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
        return jsonResponse({ error: "Invalid coordinates" }, corsHeaders, 400);
      }

      // For the Worker demo, proxy to the main API or use a KV-stored wordlist
      if (env.API_ORIGIN) {
        const resp = await fetch(`${env.API_ORIGIN}/encode?lat=${lat}&lon=${lon}`);
        const data = await resp.json();
        return jsonResponse(data, corsHeaders);
      }

      return jsonResponse({
        message: "Full encoding requires API_ORIGIN env var or KV wordlist",
        coordinates: { lat, lon },
        runtime: "cloudflare-worker",
      }, corsHeaders);
    }

    if (url.pathname === "/decode" && request.method === "GET") {
      const code = url.searchParams.get("code");
      if (!code) {
        return jsonResponse({ error: "Missing ?code= parameter" }, corsHeaders, 400);
      }

      if (env.API_ORIGIN) {
        const resp = await fetch(`${env.API_ORIGIN}/decode?code=${encodeURIComponent(code)}`);
        const data = await resp.json();
        return jsonResponse(data, corsHeaders);
      }

      return jsonResponse({
        message: "Full decoding requires API_ORIGIN env var",
        code,
        runtime: "cloudflare-worker",
      }, corsHeaders);
    }

    return jsonResponse({ error: "Not found", endpoints: ["/health", "/encode", "/decode"] }, corsHeaders, 404);
  },
};

function jsonResponse(data, headers = {}, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}
