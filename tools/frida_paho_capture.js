// Java-layer MQTT capture for the q287s6 jmq broker.
//
// The app's MQTT runs on STOCK Eclipse Paho Java (verified: unshaded
// org.eclipse.paho.client.mqttv3.* classes are loaded). Hooking the Java wire
// layer captures CONNECT/SUBSCRIBE/PUBLISH as Java objects, ABOVE TLS -- so it
// doesn't matter that the bytes ride mbedTLS/BoringSSL/whatever underneath
// (which is why the native SSL_read/SSL_write hook saw nothing).
//
// Outbound: ClientState.send(MqttWireMessage, MqttToken) -- CONNECT, SUBSCRIBE,
//   PUBLISH the app sends.
// Inbound (the device-push messages we want): CommsReceiver receives parsed
//   MqttWireMessages; we hook MqttPublish accessors / the receiver path.
//
// Output: "PAHOCAP <json>" console lines with {dir, type, topic, payload,
// connect{...}}. The CONNECT password is REDACTED to length only.
//
// Usage (spawn so hooks are live before connect):
//   frida -U -f com.eco.global.app -l tools/frida_paho_capture.js

'use strict';

const TAG = 'PAHOCAP';

function bytesToStr(jbytes) {
  if (jbytes === null) return null;
  try {
    const String = Java.use('java.lang.String');
    return String.$new(jbytes, 'UTF-8');
  } catch (e) {
    return '<' + jbytes.length + ' bytes>';
  }
}

function bytesToHex(jbytes) {
  if (jbytes === null) return null;
  const buf = Java.array('byte', jbytes);
  let s = '';
  const cap = Math.min(buf.length, 2048);
  for (let i = 0; i < cap; i++) {
    s += ((buf[i] & 0xff).toString(16)).padStart(2, '0');
  }
  return s;
}

function emit(rec) {
  console.log(TAG + ' ' + JSON.stringify(rec));
}

function describe(msg) {
  // msg is an org.eclipse.paho...MqttWireMessage subclass instance
  const rec = {};
  try {
    const cls = msg.getClass().getName();
    rec.cls = cls;
    const simple = cls.substring(cls.lastIndexOf('.') + 1);
    rec.type = simple;

    if (simple === 'MqttPublish' || simple === 'MqttReceivedMessage') {
      // getTopicName() + getMessage().getPayload()
      try { rec.topic = msg.getTopicName(); } catch (e) {}
      try {
        const m = msg.getMessage();
        const payload = m.getPayload();
        rec.payload = bytesToStr(payload);
        rec.qos = m.getQos();
      } catch (e) { rec.payload_err = '' + e; }
    } else if (simple === 'MqttSubscribe') {
      try {
        const topics = msg.getTopics ? msg.getTopics() : msg.getNames();
        rec.topics = topics ? topics.map((t) => '' + t) : null;
      } catch (e) {
        // fall back to toString which lists topics
        rec.repr = '' + msg.toString();
      }
    } else if (simple === 'MqttConnect') {
      // toString() includes clientId, keepalive, cleanSession; password is char[]
      rec.repr = '' + msg.toString();
    }
  } catch (e) {
    rec.describe_err = '' + e;
  }
  return rec;
}

function classExists(name) {
  try {
    Java.use(name);
    return true;
  } catch (e) {
    return false;
  }
}

function installHooks() {
  Java.perform(function () {
    // Outbound: every message the client sends goes through ClientState.send
    try {
      const ClientState = Java.use(
        'org.eclipse.paho.client.mqttv3.internal.ClientState'
      );
      // send(MqttWireMessage, MqttToken)
      ClientState.send.overload(
        'org.eclipse.paho.client.mqttv3.internal.wire.MqttWireMessage',
        'org.eclipse.paho.client.mqttv3.MqttToken'
      ).implementation = function (message, token) {
        try {
          const rec = describe(message);
          rec.dir = 'tx';
          emit(rec);
        } catch (e) {}
        return this.send(message, token);
      };
      console.log(TAG + ' hooked ClientState.send');
    } catch (e) {
      console.log(TAG + ' WARN ClientState.send hook failed: ' + e);
    }

    // Inbound: the CONNECT message is built by MqttConnect; capture its
    // credentials at construction (the password is only here, pre-wire).
    try {
      const MqttConnect = Java.use(
        'org.eclipse.paho.client.mqttv3.internal.wire.MqttConnect'
      );
      MqttConnect.$init.overload(
        'java.lang.String', 'int', 'boolean', 'int',
        'java.lang.String', '[C',
        'org.eclipse.paho.client.mqttv3.MqttMessage', 'java.lang.String'
      ).implementation = function (clientId, ver, clean, keepalive, user, pass, will, willDest) {
        try {
          emit({
            dir: 'tx', type: 'MqttConnect(ctor)',
            clientId: clientId, mqttVersion: ver, cleanSession: clean,
            keepalive: keepalive, username: user,
            password: pass === null ? null : '<REDACTED len=' + pass.length + '>',
          });
        } catch (e) {}
        return this.$init(clientId, ver, clean, keepalive, user, pass, will, willDest);
      };
      console.log(TAG + ' hooked MqttConnect.<init>');
    } catch (e) {
      console.log(TAG + ' note: MqttConnect ctor overload not matched (' + e + ')');
    }

    // Inbound pushes: CommsReceiver hands received messages to ClientState via
    // notifyReceivedMsg. Hook that to see PUBLISH the broker pushes.
    try {
      const ClientState = Java.use(
        'org.eclipse.paho.client.mqttv3.internal.ClientState'
      );
      ClientState.notifyReceivedMsg.implementation = function (message) {
        try {
          const rec = describe(message);
          rec.dir = 'rx';
          emit(rec);
        } catch (e) {}
        return this.notifyReceivedMsg(message);
      };
      console.log(TAG + ' hooked ClientState.notifyReceivedMsg');
    } catch (e) {
      console.log(TAG + ' WARN notifyReceivedMsg hook failed: ' + e);
    }
  });
}

// On a fresh spawn the Paho classes load lazily (only once the SDK starts its
// MQTT connection), so Java.use() faults if called too early. Poll until
// ClientState is loaded, then install the hooks exactly once.
let installed = false;
function waitAndInstall() {
  Java.perform(function () {
    if (installed) return;
    if (classExists('org.eclipse.paho.client.mqttv3.internal.ClientState')) {
      installed = true;
      installHooks();
    } else {
      setTimeout(waitAndInstall, 1000);
    }
  });
}
setTimeout(waitAndInstall, 1500);
