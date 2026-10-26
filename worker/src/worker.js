/**
 * CineBusca HLS Worker
 *
 * Rutas:
 *   GET /              → health
 *   GET /api/play      → resuelve stream DENTRO del Worker (misma IP que descarga)
 *                       ?id=TMDB&media=movie|tv&e=&s=[&season=&episode=]
 *   GET /api/hls       → proxy firmado de m3u8/segmentos
 *                       ?u=&e=&s=[&r=]
 *
 * STREAM_SIGN_KEY (secret) debe coincidir con Render.
 */

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const VIDEOAPI = "https://videoapi.la";
const VIMEOS_REF = "https://vimeos.net/";

const HOST_SUFFIXES = [
  "vimeos.net",
  "vimeos.zip",
  "videoapi.la",
  "unlimplay.com",
  "morencius.com",
  "fastream.to",
  "voe.sx",
  "embedwish.com",
  "streamwish.to",
  "streamhg.com",
  "filemoon.sx",
  "dramiyos-cdn.com",
  "acek-cdn.com",
  "vibuxer.com",
  "premilkyway.com",
  "lulustream.com",
  "vidsrc.sh",
  "vidapi.cloud",
  "pixelstreama.biz",
  "vixsrc.to",
  "streamdata.vaplayer.ru",
  "vidlink.pro",
  "vidzee.to",
  "vidfast.co",
  "doodstream.com",
  "waaw.to",
  "tnmr.org",
  "mxcontent.net",
  "mxdrop.click",
  "mixdrop",
  "empoweredfreelancerhub.site",
  "brightpathsignals.com",
  "stellarconductornexus.com",
  "playlatinsrc.co",
  "embed69",
];

const MEDIA_PATH_RE =
  /(\.m3u8|\.ts|\.m4s|\.mp4|master\.txt|\/hls[0-9]?\/|\/stream\/|\/media\/|\/pl\/|urlset|seg-)/i;

function corsHeaders(extra = {}) {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET, HEAD, OPTIONS",
    "access-control-allow-headers": "*",
    "access-control-max-age": "86400",
    ...extra,
  };
}

function b64urlDecode(s) {
  s = (s || "").replace(/-/g, "+").replace(/_/g, "/");
  const pad = s.length % 4;
  if (pad) s += "=".repeat(4 - pad);
  const bin = atob(s);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

function b64urlEncode(bytes) {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlEncodeStr(str) {
  return b64urlEncode(new TextEncoder().encode(str));
}

async function hmacMac(keyRaw, payload, ref, exp) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(keyRaw),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const msg = enc.encode(`${exp}\n${ref}\n${payload}`);
  const sig = await crypto.subtle.sign("HMAC", key, msg);
  return b64urlEncode(new Uint8Array(sig).slice(0, 16));
}

function hostAllowed(host) {
  host = (host || "").toLowerCase().replace(/\.$/, "");
  return HOST_SUFFIXES.some((s) => host === s || host.endsWith("." + s));
}

function looksLikeMedia(pathname, search) {
  return MEDIA_PATH_RE.test(pathname + search);
}

function jsonErr(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: corsHeaders({ "content-type": "application/json" }),
  });
}

async function verifyHls(urlObj, env) {
  const u = urlObj.searchParams.get("u") || "";
  const e = urlObj.searchParams.get("e") || "0";
  const s = urlObj.searchParams.get("s") || "";
  const r = urlObj.searchParams.get("r") || "";
  const key = (env.STREAM_SIGN_KEY || "").trim();
  if (!key) return { ok: false, reason: "no_sign_key" };
  if (!u || !s) {
    return {
      ok: false,
      reason: "missing_params",
      has_u: Boolean(u),
      has_s: Boolean(s),
      has_e: Boolean(urlObj.searchParams.get("e")),
      query_len: urlObj.search.length,
    };
  }

  let target, ref;
  try {
    target = new TextDecoder().decode(b64urlDecode(u));
    ref = r ? new TextDecoder().decode(b64urlDecode(r)) : "";
  } catch {
    return { ok: false, reason: "malformed" };
  }
  const exp = parseInt(e, 10);
  if (!Number.isFinite(exp) || exp < Math.floor(Date.now() / 1000)) {
    return { ok: false, reason: "expired" };
  }
  const expected = await hmacMac(key, target, ref, exp);
  if (expected !== s) return { ok: false, reason: "bad_signature" };

  let parsed;
  try {
    parsed = new URL(target);
  } catch {
    return { ok: false, reason: "bad_url" };
  }
  if (parsed.protocol !== "https:") return { ok: false, reason: "not_https" };
  if (!hostAllowed(parsed.hostname)) return { ok: false, reason: "host_denied" };
  if (!looksLikeMedia(parsed.pathname, parsed.search)) {
    return { ok: false, reason: "not_media_path" };
  }
  return { ok: true, target, ref, parsed };
}

async function verifyPlay(urlObj, env) {
  const id = (urlObj.searchParams.get("id") || "").trim();
  const media = (urlObj.searchParams.get("media") || "movie").toLowerCase();
  const season = urlObj.searchParams.get("season") || "1";
  const episode = urlObj.searchParams.get("episode") || "1";
  const e = urlObj.searchParams.get("e") || "0";
  const s = urlObj.searchParams.get("s") || "";
  const key = (env.STREAM_SIGN_KEY || "").trim();

  if (!key) return { ok: false, reason: "no_sign_key" };
  if (!id || !s) return { ok: false, reason: "missing_params" };

  const exp = parseInt(e, 10);
  if (!Number.isFinite(exp) || exp < Math.floor(Date.now() / 1000)) {
    return { ok: false, reason: "expired" };
  }

  const payload = `play:${media}:${id}:s${season}e${episode}`;
  const expected = await hmacMac(key, payload, "", exp);
  if (expected !== s) return { ok: false, reason: "bad_signature" };

  return {
    ok: true,
    id,
    media,
    season: parseInt(season, 10) || 1,
    episode: parseInt(episode, 10) || 1,
    exp,
  };
}

async function signHlsUrl(keyRaw, targetUrl, ref, exp) {
  const mac = await hmacMac(keyRaw, targetUrl, ref || "", exp);
  const params = new URLSearchParams();
  params.set("u", b64urlEncodeStr(targetUrl));
  params.set("e", String(exp));
  params.set("s", mac);
  if (ref) params.set("r", b64urlEncodeStr(ref));
  return params.toString();
}

async function rewritePlaylist(text, baseUrl, workerOrigin, keyRaw, ref, exp) {
  const lines = text.split(/\r?\n/);
  const out = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      if (/URI="/i.test(trimmed)) {
        try {
          const m = trimmed.match(/URI="([^"]+)"/i);
          if (m) {
            const abs = new URL(m[1], baseUrl).href;
            const q = await signHlsUrl(keyRaw, abs, ref, exp);
            out.push(
              trimmed.replace(/URI="[^"]+"/i, `URI="${workerOrigin}/api/hls?${q}"`)
            );
            continue;
          }
        } catch {
          /* keep */
        }
      }
      out.push(line);
      continue;
    }
    try {
      const abs = new URL(trimmed, baseUrl).href;
      const q = await signHlsUrl(keyRaw, abs, ref, exp);
      out.push(`${workerOrigin}/api/hls?${q}`);
    } catch {
      out.push(line);
    }
  }
  let body = out.join("\n");
  if (
    !body.includes("#EXT-X-STREAM-INF") &&
    body.includes("#EXTINF") &&
    !body.includes("#EXT-X-ENDLIST")
  ) {
    if (!body.includes("#EXT-X-PLAYLIST-TYPE")) {
      body = body.replace(/\s*$/, "\n#EXT-X-PLAYLIST-TYPE:VOD\n");
    }
    body = body.replace(/\s*$/, "\n#EXT-X-ENDLIST\n");
  }
  return body;
}

function collectCookies(res, jar) {
  // CF Workers: getSetCookie() o set-cookie concatenado
  try {
    const list = typeof res.headers.getSetCookie === "function"
      ? res.headers.getSetCookie()
      : [];
    if (list && list.length) {
      for (const c of list) {
        const pair = c.split(";")[0].trim();
        if (pair.includes("=")) {
          const name = pair.split("=")[0];
          jar[name] = pair;
        }
      }
      return;
    }
  } catch { /* ignore */ }
  const raw = res.headers.get("set-cookie");
  if (!raw) return;
  // puede venir varias separadas; tomar name=value
  for (const part of raw.split(/,(?=[^;]+?=)/)) {
    const pair = part.split(";")[0].trim();
    if (pair.includes("=")) {
      const name = pair.split("=")[0];
      jar[name] = pair;
    }
  }
}

function cookieHeader(jar) {
  return Object.values(jar).join("; ");
}

async function fetchText(url, headers = {}, jar = null) {
  const h = {
    "User-Agent": UA,
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
    ...headers,
  };
  if (jar && Object.keys(jar).length) {
    h["Cookie"] = cookieHeader(jar);
  }
  const r = await fetch(url, {
    headers: h,
    redirect: "follow",
    cf: { cacheTtl: 0 },
  });
  if (jar) collectCookies(r, jar);
  const text = await r.text();
  return { status: r.status, text, url: r.url, headers: r.headers };
}

function extractVimeosEmbeds(html) {
  const found = [];
  const re = /https:\/\/vimeos\.net\/embed-[A-Za-z0-9]+\.html(?:\?cf=[^"'\s]*)?/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    if (!found.includes(m[0])) found.push(m[0]);
  }
  if (!found.length) {
    const m2 = html.match(/vimeos\.net\/embed-([A-Za-z0-9]+)\.html/i);
    if (m2) found.push(`https://vimeos.net/embed-${m2[1]}.html`);
  }
  found.sort((a, b) => {
    const ac = a.includes("?cf=") ? 0 : 1;
    const bc = b.includes("?cf=") ? 0 : 1;
    return ac - bc || a.length - b.length;
  });
  return found;
}

function extractM3u8(html) {
  const found = [];
  const re = /https?:\/\/[^"'\s<>\\]+\.m3u8[^"'\s<>\\]*/gi;
  let m;
  while ((m = re.exec(html || "")) !== null) {
    const u = m[0].replace(/\\\//g, "/").replace(/\\+$/, "");
    if (!found.includes(u)) found.push(u);
  }
  return found;
}

async function resolveVideoapi(id, media, season, episode) {
  const kind = media === "tv" || media === "anime" ? media : "movie";
  let page;
  if (kind === "movie") page = `${VIDEOAPI}/e/movie/${id}`;
  else if (kind === "anime") page = `${VIDEOAPI}/e/anime/${id}/${season}/${episode}`;
  else page = `${VIDEOAPI}/e/tv/${id}/${season}/${episode}`;

  const jar = {};
  const pageRes = await fetchText(page, { Referer: VIDEOAPI + "/" }, jar);
  if (pageRes.status >= 400) {
    return { ok: false, error: `videoapi_http_${pageRes.status}` };
  }

  const embeds = extractVimeosEmbeds(pageRes.text);
  if (!embeds.length) {
    return { ok: false, error: "videoapi_no_embed" };
  }

  let m3u8s = [];
  let lastEmbed = embeds[0];
  for (const emb of embeds.slice(0, 2)) {
    lastEmbed = emb;
    const embRes = await fetchText(
      emb,
      { Referer: VIDEOAPI + "/", Origin: VIDEOAPI },
      jar
    );
    m3u8s = extractM3u8(embRes.text);
    if (m3u8s.length) break;
    if (emb.includes("?cf=")) {
      const bare = emb.split("?cf=")[0];
      const bareRes = await fetchText(
        bare,
        { Referer: VIDEOAPI + "/", Origin: VIDEOAPI },
        jar
      );
      m3u8s = extractM3u8(bareRes.text);
      if (m3u8s.length) {
        lastEmbed = bare;
        break;
      }
    }
  }

  if (!m3u8s.length) {
    return { ok: false, error: "videoapi_no_m3u8", embed: lastEmbed };
  }

  return {
    ok: true,
    m3u8: m3u8s[0],
    candidates: m3u8s,
    // Referer del embed (no solo el dominio) — hotlink protection
    ref: lastEmbed.startsWith("http") ? lastEmbed : VIMEOS_REF,
    embed: lastEmbed,
    cookies: cookieHeader(jar),
  };
}

async function handlePlay(request, env, url) {
  const checked = await verifyPlay(url, env);
  if (!checked.ok) {
    return jsonErr(403, { error: checked.reason });
  }

  const resolved = await resolveVideoapi(
    checked.id,
    checked.media,
    checked.season,
    checked.episode
  );

  if (!resolved.ok) {
    return jsonErr(404, {
      error: resolved.error || "resolve_failed",
      embed: resolved.embed || null,
    });
  }

  // NO bajamos el media desde el Worker (evita 403/1016 del CDN).
  // Devolvemos la URL limpia para que el navegador la reproduzca (IP residencial).
  return new Response(
    JSON.stringify({
      ok: true,
      provider: "worker:videoapi",
      stream_type: "hls",
      streams: [
        {
          url: resolved.m3u8,
          type: "hls",
          direct: true,
          ref: resolved.ref || VIMEOS_REF,
        },
        ...(resolved.candidates || [])
          .filter((u) => u !== resolved.m3u8)
          .slice(0, 3)
          .map((u) => ({
            url: u,
            type: "hls",
            direct: true,
            ref: resolved.ref || VIMEOS_REF,
          })),
      ],
      ref_url: resolved.ref || VIMEOS_REF,
      embed: resolved.embed || null,
    }),
    {
      status: 200,
      headers: corsHeaders({
        "content-type": "application/json",
        "cache-control": "public, max-age=30",
      }),
    }
  );
}

async function handleHls(request, env, url) {
  const checked = await verifyHls(url, env);
  if (!checked.ok) {
    const body = { error: checked.reason };
    for (const k of ["has_u", "has_s", "has_e", "query_len"]) {
      if (checked[k] !== undefined) body[k] = checked[k];
    }
    return jsonErr(403, body);
  }

  const headers = {
    "User-Agent": UA,
    Accept: "*/*",
    "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
  };
  if (checked.ref) {
    headers["Referer"] = checked.ref;
    try {
      headers["Origin"] = new URL(checked.ref).origin;
    } catch {
      /* ignore */
    }
  }

  const range = request.headers.get("Range");
  if (range) headers["Range"] = range;

  const upstream = await fetch(checked.target, {
    headers,
    redirect: "follow",
    cf: { cacheTtl: 30 },
  });

  const ct = (upstream.headers.get("content-type") || "").toLowerCase();
  const isPlaylist =
    ct.includes("mpegurl") ||
    ct.includes("m3u8") ||
    checked.parsed.pathname.toLowerCase().includes(".m3u8");

  if (isPlaylist) {
    const text = await upstream.text();
    if (!text.trimStart().startsWith("#EXTM3U")) {
      return jsonErr(502, {
        error: "not_a_playlist",
        upstream_status: upstream.status,
        head: text.slice(0, 120),
      });
    }
    const exp = parseInt(url.searchParams.get("e") || "0", 10);
    const rewritten = await rewritePlaylist(
      text,
      checked.target,
      url.origin,
      (env.STREAM_SIGN_KEY || "").trim(),
      checked.ref,
      exp
    );
    return new Response(rewritten, {
      status: 200,
      headers: corsHeaders({
        "content-type": "application/vnd.apple.mpegurl",
        "cache-control": "public, max-age=15",
      }),
    });
  }

  const outHeaders = new Headers(corsHeaders());
  const pass = ["content-type", "content-length", "accept-ranges", "content-range"];
  for (const h of pass) {
    const v = upstream.headers.get(h);
    if (v) outHeaders.set(h, v);
  }
  if (!outHeaders.has("content-type")) {
    outHeaders.set("content-type", "application/octet-stream");
  }
  outHeaders.set("cache-control", "public, max-age=60");

  return new Response(upstream.body, {
    status: upstream.status,
    headers: outHeaders,
  });
}


async function egressIp() {
  try {
    const tr = await fetch("https://www.cloudflare.com/cdn-cgi/trace");
    const tt = await tr.text();
    return (tt.match(/^ip=(.*)$/m) || [])[1] || null;
  } catch {
    return null;
  }
}

/**
 * Diagnóstico: ¿misma IP entre subrequests? ¿el CDN acepta al Worker?
 * GET /api/diag?id=438631&media=movie&e=&s=  (misma firma que /api/play)
 */
async function handleDiag(request, env, url) {
  const checked = await verifyPlay(url, env);
  if (!checked.ok) {
    return jsonErr(403, { error: checked.reason });
  }

  const ip1 = await egressIp();

  const resolved = await resolveVideoapi(
    checked.id,
    checked.media,
    checked.season,
    checked.episode
  );

  if (!resolved.ok) {
    return jsonErr(404, {
      error: resolved.error || "resolve_failed",
      ip1,
      ip2: null,
    });
  }

  const ip2 = await egressIp();

  const headers = {
    "User-Agent": UA,
    Accept: "*/*",
    "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
    Referer: resolved.ref || resolved.embed || VIMEOS_REF,
  };
  if (resolved.cookies) headers["Cookie"] = resolved.cookies;

  let status = 0;
  let head = "";
  try {
    const r = await fetch(resolved.m3u8, {
      headers,
      redirect: "follow",
      cf: { cacheTtl: 0 },
    });
    status = r.status;
    head = (await r.text()).slice(0, 80);
  } catch (err) {
    status = -1;
    head = String(err).slice(0, 80);
  }

  const sameIp = ip1 && ip2 && ip1 === ip2;
  let verdict = "unknown";
  if (ip1 && ip2 && ip1 !== ip2) {
    verdict = "ip_changes_between_subrequests";
  } else if (status === 200 && head.trimStart().startsWith("#EXTM3U")) {
    verdict = "worker_can_proxy";
  } else if (status === 403 || status === 530) {
    verdict = "cdn_blocks_cf_range";
  } else {
    verdict = "cdn_reject_other";
  }

  return new Response(
    JSON.stringify({
      ok: true,
      ip1,
      ip2,
      same_ip: sameIp,
      m3u8_status: status,
      m3u8_head: head,
      m3u8_url: (resolved.m3u8 || "").slice(0, 120),
      verdict,
    }),
    {
      status: 200,
      headers: corsHeaders({
        "content-type": "application/json",
        "cache-control": "no-store",
      }),
    }
  );
}


export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    if (url.pathname === "/") {
      return new Response("cinebusca-hls-worker ok (play+hls)", {
        headers: corsHeaders({ "content-type": "text/plain" }),
      });
    }

    if (url.pathname === "/api/play") {
      try {
        return await handlePlay(request, env, url);
      } catch (err) {
        return jsonErr(500, {
          error: "play_exception",
          detail: String(err).slice(0, 160),
        });
      }
    }

    if (url.pathname === "/api/diag") {
      try {
        return await handleDiag(request, env, url);
      } catch (err) {
        return jsonErr(500, {
          error: "diag_exception",
          detail: String(err).slice(0, 160),
        });
      }
    }

    if (url.pathname === "/api/hls") {
      try {
        return await handleHls(request, env, url);
      } catch (err) {
        return jsonErr(500, {
          error: "hls_exception",
          detail: String(err).slice(0, 160),
        });
      }
    }

    return new Response("Not found", { status: 404, headers: corsHeaders() });
  },
};