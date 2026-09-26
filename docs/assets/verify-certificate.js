/*
 * Monte-Neo certificate signature check, in the browser (no upload, no server).
 *
 * The signature covers the canonical JSON of the certificate without its "signature"
 * field, exactly as Python produces it: json.dumps(body, sort_keys=True,
 * separators=(",", ":"), ensure_ascii=False). JSON.stringify formats numbers
 * differently (1.0 -> "1"), so this file parses JSON itself and re-serializes every
 * number the way Python's repr() does.
 *
 * Works in browsers and in Node (tests use module.exports).
 */
(function (root) {
  "use strict";

  // ---- JSON parser that keeps number lexemes ------------------------------------
  function parse(text) {
    let i = 0;
    const ws = () => { while (i < text.length && " \t\n\r".includes(text[i])) i++; };
    const fail = (msg) => { throw new SyntaxError(msg + " at position " + i); };

    function value() {
      ws();
      const c = text[i];
      if (c === "{") return object();
      if (c === "[") return array();
      if (c === '"') return { t: "str", v: string() };
      if (c === "-" || (c >= "0" && c <= "9")) return number();
      for (const lit of ["true", "false", "null"]) {
        if (text.startsWith(lit, i)) { i += lit.length; return { t: "lit", raw: lit }; }
      }
      return fail("unexpected character");
    }
    function object() {
      i++; const entries = []; ws();
      if (text[i] === "}") { i++; return { t: "obj", entries }; }
      for (;;) {
        ws(); if (text[i] !== '"') fail("expected key");
        const k = string(); ws();
        if (text[i] !== ":") fail("expected ':'"); i++;
        entries.push([k, value()]); ws();
        if (text[i] === ",") { i++; continue; }
        if (text[i] === "}") { i++; return { t: "obj", entries }; }
        fail("expected ',' or '}'");
      }
    }
    function array() {
      i++; const items = []; ws();
      if (text[i] === "]") { i++; return { t: "arr", items }; }
      for (;;) {
        items.push(value()); ws();
        if (text[i] === ",") { i++; continue; }
        if (text[i] === "]") { i++; return { t: "arr", items }; }
        fail("expected ',' or ']'");
      }
    }
    function string() {
      i++; let out = "";
      for (;;) {
        if (i >= text.length) fail("unterminated string");
        const c = text[i++];
        if (c === '"') return out;
        if (c !== "\\") { out += c; continue; }
        const e = text[i++];
        const map = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };
        if (e in map) { out += map[e]; continue; }
        if (e !== "u") fail("bad escape");
        out += String.fromCharCode(parseInt(text.slice(i, i + 4), 16)); i += 4;
      }
    }
    function number() {
      const m = /^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?/.exec(text.slice(i));
      if (!m) fail("bad number");
      i += m[0].length;
      return { t: "num", raw: m[0] };
    }
    const tree = value(); ws();
    if (i !== text.length) fail("trailing data");
    return tree;
  }

  // ---- Python-compatible serialization ------------------------------------------
  function pyFloatRepr(x) {
    if (x === 0) return Object.is(x, -0) ? "-0.0" : "0.0";
    const sign = x < 0 ? "-" : "";
    const [mant, e] = Math.abs(x).toExponential().split("e");
    const exp = parseInt(e, 10);
    const digits = mant.replace(".", "");
    if (exp < -4 || exp >= 16) {
      const m = digits.length > 1 ? digits[0] + "." + digits.slice(1) : digits;
      return sign + m + "e" + (exp < 0 ? "-" : "+") + String(Math.abs(exp)).padStart(2, "0");
    }
    if (exp >= 0) {
      const intPart = digits.slice(0, exp + 1).padEnd(exp + 1, "0");
      const frac = digits.slice(exp + 1);
      return sign + intPart + "." + (frac || "0");
    }
    return sign + "0." + "0".repeat(-exp - 1) + digits;
  }

  function pyNumber(raw) {
    if (/[.eE]/.test(raw)) return pyFloatRepr(Number(raw));
    return BigInt(raw).toString();
  }

  function pyString(s) {
    let out = '"';
    for (const ch of s) {
      const code = ch.codePointAt(0);
      if (ch === '"') out += '\\"';
      else if (ch === "\\") out += "\\\\";
      else if (ch === "\n") out += "\\n";
      else if (ch === "\r") out += "\\r";
      else if (ch === "\t") out += "\\t";
      else if (ch === "\b") out += "\\b";
      else if (ch === "\f") out += "\\f";
      else if (code < 0x20) out += "\\u" + code.toString(16).padStart(4, "0");
      else out += ch;
    }
    return out + '"';
  }

  function byCodePoint(a, b) {
    const x = Array.from(a[0], (c) => c.codePointAt(0));
    const y = Array.from(b[0], (c) => c.codePointAt(0));
    for (let k = 0; k < Math.min(x.length, y.length); k++) if (x[k] !== y[k]) return x[k] - y[k];
    return x.length - y.length;
  }

  function serialize(node) {
    switch (node.t) {
      case "obj":
        return "{" + node.entries.slice().sort(byCodePoint)
          .map(([k, v]) => pyString(k) + ":" + serialize(v)).join(",") + "}";
      case "arr": return "[" + node.items.map(serialize).join(",") + "]";
      case "str": return pyString(node.v);
      case "num": return pyNumber(node.raw);
      default: return node.raw;
    }
  }

  /** Canonical payload (string) of a certificate given as JSON text. */
  function canonicalPayload(text) {
    const tree = parse(text);
    if (tree.t !== "obj") throw new Error("certificate must be a JSON object");
    return serialize({ t: "obj", entries: tree.entries.filter(([k]) => k !== "signature") });
  }

  // ---- Signature check ----------------------------------------------------------
  const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
  const hex = (buf) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");

  function publicKeyBytes(spec) {
    const text = String(spec).trim();
    if (!text.startsWith("ed25519:")) throw new Error("public key must look like 'ed25519:<base64>'");
    const raw = b64(text.slice(8));
    if (raw.length !== 32) throw new Error("Ed25519 public key must be 32 bytes");
    return raw;
  }

  /** Same result fields as Python check_signature (strategy-signature-check/1). */
  async function checkSignature(certText, expectedKey) {
    const subtle = (root.crypto || globalThis.crypto).subtle;
    const cert = JSON.parse(certText);
    const result = {
      schema: "strategy-signature-check/1",
      certificate_id: cert.certificate_id ?? null,
      verdict: cert.verdict ?? null,
      signed: !!(cert.signature && typeof cert.signature === "object"),
      valid: false, key_id: null, key_matches: null, reason: null,
    };
    if (cert.schema !== "strategy-verdict/1") throw new Error("not a strategy-verdict/1 certificate");
    if (!result.signed) { result.reason = "certificate is not signed"; return result; }
    const sig = cert.signature;
    try {
      if (sig.alg !== "ed25519") throw new Error("unsupported signature algorithm " + JSON.stringify(sig.alg));
      const raw = publicKeyBytes(sig.public_key);
      result.key_id = hex(await subtle.digest("SHA-256", raw)).slice(0, 16);
      const key = await subtle.importKey("raw", raw, { name: "Ed25519" }, false, ["verify"]);
      const data = new TextEncoder().encode(canonicalPayload(certText));
      result.valid = await subtle.verify({ name: "Ed25519" }, key, b64(String(sig.value)), data);
      if (!result.valid) { result.reason = "signature does not match the certificate"; return result; }
      if (expectedKey && String(expectedKey).trim()) {
        const want = publicKeyBytes(expectedKey);
        result.key_matches = want.length === raw.length && want.every((b, k) => b === raw[k]);
        if (!result.key_matches) result.reason = "signed with a different key than the one expected";
      } else {
        result.reason = "integrity only: pass the issuer's public key to check who signed";
      }
    } catch (err) {
      result.valid = false;
      result.reason = "signature does not match: " + err.message;
    }
    return result;
  }

  const api = { parse, canonicalPayload, pyFloatRepr, checkSignature };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.MonteNeoVerify = api;

  // ---- Page wiring (only when the page elements exist) --------------------------
  function el(tag, text, cls) {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }

  function render(out, result, certText) {
    out.replaceChildren();
    const ok = result.valid && result.key_matches !== false;
    const head = ok
      ? (result.key_matches ? "✅ Valid signature from the expected key" : "✅ Valid signature (integrity only)")
      : (result.signed ? "❌ Signature check failed" : "⚠️ Certificate is not signed");
    out.append(el("p", head, "mn-verify-status"));
    if (!ok && result.signed) {
      out.append(el("p", "Do not trust the fields below: they are what the file says, and the file was changed after signing or signed by someone else."));
    }
    const rows = [
      ["Verdict", result.verdict], ["Certificate id", result.certificate_id],
      ["Signing key id", result.key_id], ["Matches expected key", result.key_matches === null ? "not checked" : String(result.key_matches)],
      ["Note", result.reason],
    ];
    const table = el("table");
    for (const [k, v] of rows) {
      const tr = el("tr"); tr.append(el("th", k), el("td", v === null || v === undefined ? "—" : String(v))); table.append(tr);
    }
    out.append(table);
    try {
      const cert = JSON.parse(certText);
      if (Array.isArray(cert.checks)) {
        const checks = el("table");
        const hdr = el("tr"); ["check", "category", "status", "summary"].forEach((h) => hdr.append(el("th", h))); checks.append(hdr);
        for (const c of cert.checks) {
          const tr = el("tr");
          [c.id, c.category, c.status, c.summary].forEach((v) => tr.append(el("td", String(v ?? ""))));
          checks.append(tr);
        }
        out.append(el("p", "Checks recorded in the certificate:"), checks);
      }
    } catch (_) { /* already reported above */ }
  }

  function wire() {
    const form = document.getElementById("mn-verify-form");
    if (!form || form.dataset.wired) return;
    form.dataset.wired = "1";
    const certBox = document.getElementById("mn-cert");
    const keyBox = document.getElementById("mn-key");
    const fileBox = document.getElementById("mn-cert-file");
    const out = document.getElementById("mn-verify-result");
    if (!(root.crypto && root.crypto.subtle)) {
      out.replaceChildren(el("p", "This browser has no WebCrypto; use `monte-neo verify --check-signature` instead."));
      return;
    }
    const run = async () => {
      try {
        render(out, await checkSignature(certBox.value, keyBox.value), certBox.value);
      } catch (err) {
        out.replaceChildren(el("p", "❌ " + err.message + " (Ed25519 needs a current browser; or run monte-neo verify --check-signature)"));
      }
    };
    form.addEventListener("submit", (ev) => { ev.preventDefault(); run(); });
    fileBox.addEventListener("change", async () => {
      if (fileBox.files[0]) certBox.value = await fileBox.files[0].text();
    });
    const params = new URLSearchParams(root.location.search);
    if (params.get("key")) keyBox.value = params.get("key");
    const url = params.get("cert");
    if (url && /^https:\/\//.test(url)) {
      out.replaceChildren(el("p", "Loading " + url + " …"));
      fetch(url).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.text(); })
        .then((text) => { certBox.value = text; return run(); })
        .catch((err) => out.replaceChildren(el("p", "❌ Could not load the certificate: " + err.message)));
    }
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
    else wire();
    // MkDocs Material instant navigation swaps pages without a reload.
    if (root.document$ && root.document$.subscribe) root.document$.subscribe(wire);
  }
})(typeof window !== "undefined" ? window : globalThis);
