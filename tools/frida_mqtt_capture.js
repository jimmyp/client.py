// Native MQTT capture for the ngiot jmq broker (q287s6).
//
// The app's device-presence/push connection runs over MQTT-over-TLS via Eclipse
// Paho (Aliyun LinkKit). It uses a raw SSLSocket that the Java proxy-override
// unpinning scripts do NOT route through mitmproxy, so the existing REST rig
// never sees it. Instead of proxying, we tap the TLS layer directly: hook
// BoringSSL SSL_read / SSL_write inside the app and dump the plaintext MQTT
// bytes as they cross the socket. This needs no proxy and no CA trust changes.
//
// Output: lines prefixed "MQTTCAP " containing JSON {dir, len, hex} on stdout,
// which the host-side tools/capture_mqtt.sh decodes into MQTT packets. We print
// hex (not utf8) because MQTT is a binary protocol; the host decoder parses
// CONNECT/SUBSCRIBE/PUBLISH and redacts credentials.
//
// Usage (spawn so the hooks are live before Paho connects):
//   frida -U -f com.eco.global.app -l tools/frida_mqtt_capture.js
//
// Why SSL_read/SSL_write and not the socket fd: TLS is decrypted in BoringSSL,
// so the fd carries ciphertext. SSL_* give us plaintext. Android's system TLS
// is BoringSSL exposed via libssl.so; Conscrypt calls into the same.

'use strict';

const TAG = 'MQTTCAP';

// Only dump buffers that look like MQTT so we don't drown in TLS app-data from
// the REST/HTTP2 sockets sharing the same SSL_* functions. MQTT fixed header:
// high nibble of byte 0 is the packet type (1..14), low nibble flags.
const MQTT_TYPES = {
  1: 'CONNECT', 2: 'CONNACK', 3: 'PUBLISH', 4: 'PUBACK',
  8: 'SUBSCRIBE', 9: 'SUBACK', 12: 'PINGREQ', 13: 'PINGRESP', 14: 'DISCONNECT',
};

function looksLikeMqtt(bytes, len) {
  if (len < 2) return false;
  const type = bytes[0] >> 4;
  return MQTT_TYPES[type] !== undefined;
}

function hexOf(ptr, len) {
  // cap dump size; push payloads are small, CONNECT is the biggest
  const cap = Math.min(len, 4096);
  const buf = Memory.readByteArray(ptr, cap);
  const u8 = new Uint8Array(buf);
  let s = '';
  for (let i = 0; i < u8.length; i++) {
    s += u8[i].toString(16).padStart(2, '0');
  }
  return s;
}

function emit(dir, ptr, len) {
  const head = Memory.readByteArray(ptr, Math.min(len, 2));
  const bytes = new Uint8Array(head);
  if (!looksLikeMqtt(bytes, len)) return;
  const type = MQTT_TYPES[bytes[0] >> 4];
  const rec = { dir: dir, type: type, len: len, hex: hexOf(ptr, len) };
  send(rec); // structured channel
  console.log(TAG + ' ' + JSON.stringify({ dir: dir, type: type, len: len }));
}

function hookSsl(libname) {
  const ssl_read = Module.findExportByName(libname, 'SSL_read');
  const ssl_write = Module.findExportByName(libname, 'SSL_write');
  if (!ssl_read || !ssl_write) return false;

  // int SSL_read(SSL *ssl, void *buf, int num) -> bytes read into buf on return
  Interceptor.attach(ssl_read, {
    onEnter(args) { this.buf = args[1]; },
    onLeave(retval) {
      const n = retval.toInt32();
      if (n > 0 && this.buf) {
        try { emit('rx', this.buf, n); } catch (e) {}
      }
    },
  });

  // int SSL_write(SSL *ssl, const void *buf, int num) -> buf valid on enter
  Interceptor.attach(ssl_write, {
    onEnter(args) {
      const n = args[2].toInt32();
      if (n > 0) {
        try { emit('tx', args[1], n); } catch (e) {}
      }
    },
  });

  console.log(TAG + ' hooked SSL_read/SSL_write in ' + libname);
  return true;
}

function init() {
  // Android system TLS is BoringSSL in libssl.so; some builds statically link it
  // into Conscrypt (libjavacrypto.so / libconscrypt_jni.so). Try them in order.
  const candidates = ['libssl.so', 'libjavacrypto.so', 'libconscrypt_jni.so'];
  let hooked = false;
  for (const lib of candidates) {
    try { if (hookSsl(lib)) hooked = true; } catch (e) {}
  }
  if (!hooked) {
    console.log(TAG + ' WARN: no SSL_read/SSL_write export found; '
      + 'enumerate modules and look for the TLS lib');
  }
}

// Give the app a beat to load its native TLS lib, then hook.
setTimeout(init, 1500);
