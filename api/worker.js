const encoder = new TextEncoder();

function jsonResponse(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

function parseJson(request) {
  return request.json().catch(() => null);
}

function parseOrigins(raw) {
  if (!raw) return [];
  return raw.split(",").map((o) => o.trim()).filter(Boolean);
}

function applyCors(request, response, allowedOrigins) {
  const origin = request.headers.get("origin");
  if (!origin || allowedOrigins.length === 0) return response;
  if (!allowedOrigins.includes(origin)) return response;
  const headers = new Headers(response.headers);
  headers.set("Access-Control-Allow-Origin", origin);
  headers.set("Vary", "Origin");
  headers.set("Access-Control-Allow-Headers", "Authorization, Content-Type");
  headers.set("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
  return new Response(response.body, { status: response.status, headers });
}

function addSecurityHeaders(response) {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("Content-Security-Policy", "default-src 'none'");
  return new Response(response.body, { status: response.status, headers });
}

function base64UrlEncode(data) {
  return btoa(String.fromCharCode(...new Uint8Array(data)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function base64UrlDecode(input) {
  const padded = input + "=".repeat((4 - (input.length % 4)) % 4);
  const base64 = padded.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(base64);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

async function hmacSha256(secret, message) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(message)));
}

async function createToken(payload, secret) {
  const payloadJson = JSON.stringify(payload);
  const payloadB64 = base64UrlEncode(encoder.encode(payloadJson));
  const signature = await hmacSha256(secret, payloadB64);
  return `v1.${payloadB64}.${base64UrlEncode(signature)}`;
}

async function verifyToken(token, secret) {
  const parts = token.split(".");
  if (parts.length !== 3 || parts[0] !== "v1") return null;
  const [_, payloadB64, signatureB64] = parts;
  const expected = await hmacSha256(secret, payloadB64);
  const actual = base64UrlDecode(signatureB64);
  if (expected.length !== actual.length) return null;
  for (let i = 0; i < expected.length; i += 1) {
    if (expected[i] !== actual[i]) return null;
  }
  const payload = JSON.parse(new TextDecoder().decode(base64UrlDecode(payloadB64)));
  if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) return null;
  return payload;
}

async function pbkdf2Hash(password, salt, iterations = 120000) {
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    "PBKDF2",
    false,
    ["deriveBits"]
  );
  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      salt: encoder.encode(salt),
      iterations,
      hash: "SHA-256",
    },
    keyMaterial,
    256
  );
  return base64UrlEncode(new Uint8Array(bits));
}

async function hashPassword(password) {
  const salt = crypto.randomUUID();
  const hash = await pbkdf2Hash(password, salt);
  return `pbkdf2$120000$${salt}$${hash}`;
}

async function verifyPassword(password, stored) {
  const parts = stored.split("$");
  if (parts.length !== 4) return false;
  const iterations = Number(parts[1]);
  const salt = parts[2];
  const hash = parts[3];
  const candidate = await pbkdf2Hash(password, salt, iterations);
  return candidate === hash;
}

function deriveStream(key, length) {
  const digest = new TextEncoder().encode(key);
  let stream = new Uint8Array(digest);
  while (stream.length < length) {
    stream = new Uint8Array([...stream, ...digest]);
  }
  return stream.slice(0, length);
}

function encodeTotpSecret(secret, key) {
  const secretBytes = encoder.encode(secret);
  const stream = deriveStream(key, secretBytes.length);
  const obfuscated = secretBytes.map((b, i) => b ^ stream[i]);
  return base64UrlEncode(obfuscated);
}

function decodeTotpSecret(encoded, key) {
  const secretBytes = base64UrlDecode(encoded);
  const stream = deriveStream(key, secretBytes.length);
  const decoded = secretBytes.map((b, i) => b ^ stream[i]);
  return new TextDecoder().decode(decoded);
}

function base32Decode(input) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const clean = input.replace(/=+$/, "").toUpperCase();
  let bits = "";
  for (const char of clean) {
    const idx = alphabet.indexOf(char);
    if (idx === -1) continue;
    bits += idx.toString(2).padStart(5, "0");
  }
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  }
  return new Uint8Array(bytes);
}

function base32Encode(bytes) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  bytes.forEach((byte) => {
    bits += byte.toString(2).padStart(8, "0");
  });
  let output = "";
  for (let i = 0; i + 5 <= bits.length; i += 5) {
    const chunk = bits.slice(i, i + 5);
    output += alphabet[parseInt(chunk, 2)];
  }
  const remaining = bits.length % 5;
  if (remaining) {
    const chunk = bits.slice(bits.length - remaining).padEnd(5, "0");
    output += alphabet[parseInt(chunk, 2)];
  }
  return output;
}

async function totpAt(secret, timestamp) {
  const key = base32Decode(secret);
  const counter = Math.floor(timestamp / 30);
  const msg = new Uint8Array(8);
  const view = new DataView(msg.buffer);
  view.setUint32(4, counter, false);
  const cryptoKey = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
  const digest = new Uint8Array(await crypto.subtle.sign("HMAC", cryptoKey, msg));
  const offset = digest[digest.length - 1] & 0x0f;
  const code = ((digest[offset] & 0x7f) << 24) |
    ((digest[offset + 1] & 0xff) << 16) |
    ((digest[offset + 2] & 0xff) << 8) |
    (digest[offset + 3] & 0xff);
  return String(code % 1000000).padStart(6, "0");
}

async function verifyTotp(secret, code) {
  if (!/^[0-9]{6}$/.test(code)) return false;
  const now = Math.floor(Date.now() / 1000);
  for (let offset = -1; offset <= 1; offset += 1) {
    const candidate = await totpAt(secret, now + offset * 30);
    if (candidate === code) return true;
  }
  return false;
}

const rateLimiter = new Map();

function checkRateLimit(key, maxRequests, windowSeconds) {
  const now = Date.now();
  const windowStart = now - windowSeconds * 1000;
  const events = rateLimiter.get(key) || [];
  const trimmed = events.filter((t) => t > windowStart);
  if (trimmed.length >= maxRequests) {
    rateLimiter.set(key, trimmed);
    return { allowed: false, resetAfter: Math.ceil((trimmed[0] + windowSeconds * 1000 - now) / 1000) };
  }
  trimmed.push(now);
  rateLimiter.set(key, trimmed);
  return { allowed: true, resetAfter: windowSeconds };
}

async function handleRegister(request, env) {
  const body = await parseJson(request);
  if (!body || !body.email || !body.password) {
    return jsonResponse({ error: "Invalid payload" }, 400);
  }
  const email = body.email.toLowerCase();
  const allowRegistration = env.ALLOW_REGISTRATION !== "false";
  if (!allowRegistration) {
    const count = await env.DB.prepare("SELECT COUNT(*) as count FROM users").first();
    if (count.count > 0) return jsonResponse({ error: "Registration is disabled" }, 403);
  }
  const existing = await env.DB.prepare("SELECT id FROM users WHERE email = ?").bind(email).first();
  if (existing) return jsonResponse({ error: "User already exists" }, 409);
  const isAdmin = !allowRegistration;
  const passwordHash = await hashPassword(body.password);
  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  await env.DB.prepare(
    "INSERT INTO users (id, email, password_hash, is_admin, created_at, mfa_secret, mfa_enabled) VALUES (?, ?, ?, ?, ?, ?, ?)"
  )
    .bind(id, email, passwordHash, isAdmin ? 1 : 0, now, null, 0)
    .run();
  return jsonResponse({ id, email, is_admin: isAdmin, mfa_enabled: false, created_at: now });
}

async function handleLogin(request, env) {
  const body = await parseJson(request);
  if (!body || !body.email || !body.password) {
    return jsonResponse({ error: "Invalid payload" }, 400);
  }
  const email = body.email.toLowerCase();
  const user = await env.DB.prepare("SELECT * FROM users WHERE email = ?").bind(email).first();
  if (!user) return jsonResponse({ error: "Invalid credentials" }, 401);
  const valid = await verifyPassword(body.password, user.password_hash);
  if (!valid) return jsonResponse({ error: "Invalid credentials" }, 401);
  if (user.mfa_enabled) {
    if (!body.totp) return jsonResponse({ error: "MFA code required" }, 401);
    const secret = decodeTotpSecret(user.mfa_secret, env.MFA_SECRET_KEY || env.TOKEN_SECRET);
    const ok = await verifyTotp(secret, body.totp);
    if (!ok) return jsonResponse({ error: "Invalid MFA code" }, 401);
  }
  const now = Math.floor(Date.now() / 1000);
  const payload = { sub: user.id, email: user.email, iat: now, exp: now + Number(env.TOKEN_TTL_SECONDS || 3600) };
  const token = await createToken(payload, env.TOKEN_SECRET);
  return jsonResponse({ token });
}

async function getUserFromRequest(request, env) {
  const auth = request.headers.get("authorization") || "";
  if (!auth.toLowerCase().startsWith("bearer ")) return null;
  const token = auth.split(" ", 2)[1];
  const payload = await verifyToken(token, env.TOKEN_SECRET);
  if (!payload) return null;
  return env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(payload.sub).first();
}

async function handleMe(request, env) {
  const user = await getUserFromRequest(request, env);
  if (!user) return jsonResponse({ error: "Not authenticated" }, 401);
  return jsonResponse({
    id: user.id,
    email: user.email,
    is_admin: Boolean(user.is_admin),
    mfa_enabled: Boolean(user.mfa_enabled),
    created_at: user.created_at,
  });
}

async function handleMfaEnroll(request, env) {
  const user = await getUserFromRequest(request, env);
  if (!user) return jsonResponse({ error: "Not authenticated" }, 401);
  const secret = base32Encode(crypto.getRandomValues(new Uint8Array(20)));
  const encoded = encodeTotpSecret(secret, env.MFA_SECRET_KEY || env.TOKEN_SECRET);
  await env.DB.prepare("UPDATE users SET mfa_secret = ? WHERE id = ?").bind(encoded, user.id).run();
  const otpauthUrl = `otpauth://totp/Victus:${user.email}?secret=${secret}&issuer=Victus`;
  return jsonResponse({ secret, otpauth_url: otpauthUrl });
}

async function handleMfaVerify(request, env) {
  const user = await getUserFromRequest(request, env);
  if (!user) return jsonResponse({ error: "Not authenticated" }, 401);
  if (!user.mfa_secret) return jsonResponse({ error: "MFA not enrolled" }, 400);
  const body = await parseJson(request);
  if (!body || !body.code) return jsonResponse({ error: "Invalid payload" }, 400);
  const secret = decodeTotpSecret(user.mfa_secret, env.MFA_SECRET_KEY || env.TOKEN_SECRET);
  const ok = await verifyTotp(secret, body.code);
  if (!ok) return jsonResponse({ error: "Invalid MFA code" }, 401);
  await env.DB.prepare("UPDATE users SET mfa_enabled = 1 WHERE id = ?").bind(user.id).run();
  return jsonResponse({ ok: true, mfa_enabled: true });
}

export default {
  async fetch(request, env) {
    const allowedOrigins = parseOrigins(env.CORS_ALLOW_ORIGINS || "");
    if (request.method === "OPTIONS") {
      const response = new Response(null, { status: 204 });
      return applyCors(request, addSecurityHeaders(response), allowedOrigins);
    }

    const url = new URL(request.url);
    const path = url.pathname;

    if (["/auth/register", "/auth/login"].includes(path)) {
      const rateKey = `${path}:${request.headers.get("cf-connecting-ip") || "unknown"}`;
      const limit = checkRateLimit(rateKey, Number(env.RATE_LIMIT_PER_MINUTE || 30), Number(env.RATE_LIMIT_WINDOW_SECONDS || 60));
      if (!limit.allowed) {
        const response = jsonResponse({ error: "Rate limit exceeded" }, 429, { "Retry-After": String(limit.resetAfter) });
        return applyCors(request, addSecurityHeaders(response), allowedOrigins);
      }
    }

    let response;
    if (path === "/health" && request.method === "GET") {
      response = jsonResponse({
        status: "ok",
        version: env.VICTUS_VERSION || "0.1.0-server",
        time: new Date().toISOString(),
      });
    } else if (path === "/auth/register" && request.method === "POST") {
      response = await handleRegister(request, env);
    } else if (path === "/auth/login" && request.method === "POST") {
      response = await handleLogin(request, env);
    } else if (path === "/auth/mfa/enroll" && request.method === "POST") {
      response = await handleMfaEnroll(request, env);
    } else if (path === "/auth/mfa/verify" && request.method === "POST") {
      response = await handleMfaVerify(request, env);
    } else if (path === "/me" && request.method === "GET") {
      response = await handleMe(request, env);
    } else {
      response = jsonResponse({ error: "Not found" }, 404);
    }

    return applyCors(request, addSecurityHeaders(response), allowedOrigins);
  },
};
