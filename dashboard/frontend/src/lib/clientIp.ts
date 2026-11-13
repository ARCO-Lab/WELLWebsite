// The visitor's IP address, which the backend uses for its per-visitor limits (queued exports).
//
// X-Forwarded-For is trusted only from the site's own reverse proxies, listed by address in TRUSTED_PROXY_IPS
// (comma-separated; set for the dashboard service in docker-compose.yml). This server is also reachable directly on
// its published port, where anyone can send any X-Forwarded-For, so a request from any other address is identified
// by the address of its connection. From a trusted proxy, the client is the rightmost X-Forwarded-For entry that
// isn't itself a trusted proxy: each proxy appends the address it saw, so entries to the right of the client were
// added by proxies in the chain, and entries to its left are whatever the browser sent.
//
// If the [client-ip] log lines below show connection=172.x or 10.x (a Docker gateway: Docker's userland proxy
// hides the real peer), every visitor shares one address, so the per-visitor export limit acts site-wide. Don't
// fix that by adding the gateway (`docker network inspect <network>` shows it) to TRUSTED_PROXY_IPS unless port
// 8081 is firewalled to the front proxy, or faked headers on direct requests are believed again. A single sampled
// line can be a local or direct :8081 request, so look at several before deciding.

import type { IncomingMessage } from "http";

type Request = Pick<IncomingMessage, "headers" | "socket">;

// "::ffff:192.0.2.1" (an IPv4 address on an IPv6 socket) is 192.0.2.1.
function normalize(address: string): string {
  const trimmed = address.trim();
  return trimmed.toLowerCase().startsWith("::ffff:") && trimmed.includes(".") ? trimmed.slice(7) : trimmed;
}

// The addresses in TRUSTED_PROXY_IPS (or `value`), normalized.
export function trustedProxies(value = process.env.TRUSTED_PROXY_IPS || ""): Set<string> {
  return new Set(value.split(",").map(normalize).filter(Boolean));
}

// The visitor's address for this request, by the rules at the top of this file.
export function clientIp(req: Request, trusted: Set<string> = trustedProxies()): string {
  const peer = normalize(req.socket?.remoteAddress || "");
  if (!trusted.has(peer)) return peer;
  const header = req.headers["x-forwarded-for"];
  const hops = (Array.isArray(header) ? header.join(",") : header || "").split(",").map(normalize).filter(Boolean);
  for (let i = hops.length - 1; i >= 0; i--) {
    if (!trusted.has(hops[i])) return hops[i];
  }
  return hops[0] || peer; // every entry is a trusted proxy: the request started at one of them
}

// Logs, at most every 10 minutes, what a request's connection address and X-Forwarded-For look like and which
// address was chosen, so whoever runs the site can check TRUSTED_PROXY_IPS against what really arrives.
const LOG_EVERY_MS = 10 * 60 * 1000;
let lastLogged = 0;

export function logClientIpSample(req: Request, chosen: string, now = Date.now()): boolean {
  if (now - lastLogged < LOG_EVERY_MS) return false;
  lastLogged = now;
  console.info(
    `[client-ip] connection=${req.socket?.remoteAddress || "-"} x-forwarded-for=${
      req.headers["x-forwarded-for"] || "-"
    } trusted=${process.env.TRUSTED_PROXY_IPS || "-"} chosen=${chosen || "-"}`
  );
  return true;
}
