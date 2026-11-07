/* ==========================================================
 *
 *  CC Journal — WhatsApp sidecar (Baileys)
 *  Developed by: Qiyas CC
 *  Copyright (c) 2026 Qiyas CC. All Rights Reserved.
 *
 *  Django bu süreci plugin etkinleştirilince başlatır. Görevi:
 *   - WhatsApp'a Baileys ile bağlanmak (multi-file auth state, kalıcı oturum)
 *   - Bağlantı yoksa QR üretip /status üzerinden sunmak (admin tarar)
 *   - /send ile {number, message} alıp mesaj göndermek
 *
 *  Token ile korunur (yalnız yerel Django erişebilsin). Tek dış port: HTTP.
 * ========================================================== */
'use strict';

const express = require('express');
const QRCode = require('qrcode');
const pino = require('pino');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.env.WA_PORT || '8782', 10);
const TOKEN = process.env.WA_TOKEN || '';
const AUTH_DIR = process.env.WA_AUTH_DIR || path.join(__dirname, 'auth');
// Gelen mesaj köprüsü: hızlı hakem yanıtı ("1"/"2") Django'ya iletilir,
// dönen "reply" kullanıcıya geri yazılır. Boşsa devre dışı.
const HOOK_URL = process.env.WA_HOOK_URL || '';
const HOOK_SECRET = process.env.WA_HOOK_SECRET || '';

async function forwardInbound(fromJid, text) {
  if (!HOOK_URL || !text) return;
  const address = String(fromJid || '').split('@')[0].split(':')[0];
  if (!address) return;
  try {
    const res = await fetch(HOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json',
                 'X-CCJ-Hook-Secret': HOOK_SECRET },
      body: JSON.stringify({ channel: 'whatsapp', address, text }),
    });
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.reply && sock) {
      await sock.sendMessage(fromJid, { text: data.reply });
    }
  } catch (_) { /* köprü hatası gönderimi etkilemesin */ }
}

let sock = null;
let state = {
  status: 'starting',     // starting | qr | connected | disconnected
  qr: null,               // data-URL PNG (varsa)
  me: null,               // bağlı numara
  lastError: null,
  startedAt: Date.now(),
};

const logger = pino({ level: 'warn' });

async function startSock() {
  // MOCK modu: dış ağ olmadan (CI/demo) QR + bağlantı + gönderim akışını doğrulamak için.
  if (process.env.WA_MOCK === '1') {
    state.status = 'qr';
    state.qr = await QRCode.toDataURL('ccjournal-mock-qr-' + Date.now());
    // WA_MOCK_CONNECT=1 ise kısa süre sonra "bağlandı" simüle et
    if (process.env.WA_MOCK_CONNECT === '1') {
      setTimeout(() => { state.status = 'connected'; state.qr = null; state.me = '999000111'; }, 1200);
    }
    return;
  }
  // Baileys ESM olabilir; dinamik import ile uyumluluk
  const baileys = await import('@whiskeysockets/baileys');
  const makeWASocket = baileys.default || baileys.makeWASocket;
  const { useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = baileys;

  fs.mkdirSync(AUTH_DIR, { recursive: true });
  const { state: authState, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  let version;
  try { ({ version } = await fetchLatestBaileysVersion()); } catch (_) {}

  sock = makeWASocket({ version, auth: authState, logger, printQRInTerminal: false });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('messages.upsert', async (m) => {
    try {
      for (const msg of (m.messages || [])) {
        if (!msg.message || msg.key.fromMe) continue;
        const jid = msg.key.remoteJid || '';
        if (!jid.endsWith('@s.whatsapp.net')) continue;   // yalnız birebir sohbet
        const text = msg.message.conversation
          || (msg.message.extendedTextMessage && msg.message.extendedTextMessage.text)
          || '';
        if (text) await forwardInbound(jid, text.trim());
      }
    } catch (_) { /* dinleyici asla süreci düşürmesin */ }
  });

  sock.ev.on('connection.update', async (u) => {
    const { connection, lastDisconnect, qr } = u;
    if (qr) {
      state.status = 'qr';
      try { state.qr = await QRCode.toDataURL(qr); } catch (_) { state.qr = null; }
    }
    if (connection === 'open') {
      state.status = 'connected';
      state.qr = null;
      state.me = (sock.user && sock.user.id) ? sock.user.id.split(':')[0] : null;
      state.lastError = null;
    } else if (connection === 'close') {
      const code = lastDisconnect && lastDisconnect.error &&
        lastDisconnect.error.output && lastDisconnect.error.output.statusCode;
      state.status = 'disconnected';
      state.me = null;
      // çıkış (loggedOut) değilse yeniden bağlan
      if (code !== DisconnectReason.loggedOut) {
        setTimeout(() => startSock().catch(e => { state.lastError = String(e); }), 2500);
      } else {
        // oturum kapandı: auth temizle, yeni QR
        try { fs.rmSync(AUTH_DIR, { recursive: true, force: true }); } catch (_) {}
        setTimeout(() => startSock().catch(e => { state.lastError = String(e); }), 1000);
      }
    }
  });
}

// --- HTTP API (token korumalı) ---
const app = express();
app.use(express.json({ limit: '256kb' }));

function auth(req, res, next) {
  if (TOKEN && req.get('X-WA-Token') !== TOKEN) return res.status(401).json({ error: 'unauthorized' });
  next();
}

app.get('/health', (req, res) => res.json({ ok: true, status: state.status }));

app.get('/sent', auth, (req, res) => res.json({ sent: state.sent || [] }));

app.get('/status', auth, (req, res) => {
  res.json({
    status: state.status, qr: state.qr, me: state.me,
    lastError: state.lastError, uptime: Math.floor((Date.now() - state.startedAt) / 1000),
  });
});

// numarayı WhatsApp JID'ine çevir (basit; uluslararası format beklenir)
function toJid(number) {
  const digits = String(number).replace(/[^0-9]/g, '');
  return digits ? `${digits}@s.whatsapp.net` : null;
}

app.post('/send', auth, async (req, res) => {
  const { number, message } = req.body || {};
  if (!number || !message) return res.status(400).json({ error: 'number and message required' });
  // MOCK: gerçek socket olmadan gönderimi kabul et + kaydet (test/demo)
  if (process.env.WA_MOCK === '1') {
    state.sent = state.sent || [];
    state.sent.push({ number: String(number), message: String(message), at: Date.now() });
    return res.json({ ok: true, mock: true });
  }
  if (state.status !== 'connected' || !sock) return res.status(409).json({ error: 'not connected' });
  const jid = toJid(number);
  if (!jid) return res.status(400).json({ error: 'invalid number' });
  try {
    const [result] = await sock.onWhatsApp(jid).catch(() => [null]);
    if (result && result.exists === false) return res.status(404).json({ error: 'number not on whatsapp' });
    await sock.sendMessage(jid, { text: String(message) });
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

app.post('/logout', auth, async (req, res) => {
  try { if (sock) await sock.logout(); } catch (_) {}
  try { fs.rmSync(AUTH_DIR, { recursive: true, force: true }); } catch (_) {}
  state.status = 'disconnected'; state.me = null; state.qr = null;
  res.json({ ok: true });
  setTimeout(() => startSock().catch(e => { state.lastError = String(e); }), 800);
});

app.listen(PORT, '127.0.0.1', () => {
  startSock().catch(e => { state.status = 'disconnected'; state.lastError = String(e); });
});
