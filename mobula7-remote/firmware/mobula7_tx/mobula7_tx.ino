// Mobula7 remote (TX): phone page over Wi-Fi + ARM/KILL buttons -> ESP-NOW.
//
// Phone: join Wi-Fi "Mobula7-Remote" (password "mobula7fly"), open
// http://192.168.4.1
//
// Wiring (see mobula7-remote/README.md):
//   ARM  button: D25 <-> GND
//   KILL button: D26 <-> GND
//
// Requires the esp32 Arduino core 3.x, the Mobula7Link library and the
// "WebSockets" library by Markus Sattler.

#include <Mobula7Link.h>
#include <WebServer.h>
#include <WebSocketsServer.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

#include "control_page.h"

static const char* kSsid = "Mobula7-Remote";
static const char* kPassword = "mobula7fly";
static const int kArmPin = 25;
static const int kKillPin = 26;
static const int kLedPin = 2;
static const uint32_t kSendPeriodMs = 20;    // ~50 Hz to the drone
static const uint32_t kStatusPeriodMs = 200;  // status to the phone
static const uint32_t kDebounceMs = 20;
static const uint8_t kBroadcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

static WebServer g_http(80);
static WebSocketsServer g_ws(81);
static m7::TxController g_ctrl;

static m7::StickMsg g_sticks = {m7::kChMid, m7::kChMid, m7::kChLow, m7::kChMid, false, false};
static uint32_t g_last_phone_ms = 0;
static bool g_calib_request = false;
static int g_client = -1;  // only the most recent phone is kept

struct Button {
  int pin;
  bool pressed;
  bool raw;
  uint32_t changed_ms;
  void begin() {
    pinMode(pin, INPUT_PULLUP);
    raw = pressed = digitalRead(pin) == LOW;
    changed_ms = millis();
  }
  void update(uint32_t now) {
    bool r = digitalRead(pin) == LOW;  // active low
    if (r != raw) {
      raw = r;
      changed_ms = now;
    } else if (r != pressed && (uint32_t)(now - changed_ms) >= kDebounceMs) {
      pressed = r;
    }
  }
};
static Button g_arm = {kArmPin, false, false, 0};
static Button g_kill = {kKillPin, false, false, 0};

static void on_ws_event(uint8_t num, WStype_t type, uint8_t* payload, size_t len) {
  switch (type) {
    case WStype_CONNECTED:
      if (g_client >= 0 && g_client != num) g_ws.disconnect(g_client);
      g_client = num;
      break;
    case WStype_DISCONNECTED:
      if (g_client == num) g_client = -1;
      break;
    case WStype_TEXT: {
      if (num != g_client) break;
      m7::StickMsg m;
      if (!m7::parse_stick_msg((const char*)payload, len, &m)) break;
      g_sticks = m;
      g_last_phone_ms = millis();
      if (m.calib) g_calib_request = true;
      break;
    }
    default:
      break;
  }
}

static void start_wifi_and_radio() {
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(kSsid, kPassword, m7::kWifiChannel);
  if (esp_now_init() != ESP_OK) {
    Serial.println("esp_now_init failed");
    return;
  }
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, kBroadcast, sizeof(kBroadcast));
  peer.channel = m7::kWifiChannel;
  peer.ifidx = WIFI_IF_AP;
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) != ESP_OK) Serial.println("esp_now_add_peer failed");
}

static void start_servers() {
  g_http.on("/", HTTP_GET, [] {
    g_http.sendHeader("Cache-Control", "no-store");
    g_http.send_P(200, "text/html; charset=utf-8", CONTROL_PAGE);
  });
  g_http.onNotFound([] {
    g_http.sendHeader("Location", "http://192.168.4.1/");
    g_http.send(302, "text/plain", "");
  });
  g_http.begin();
  g_ws.begin();
  g_ws.onEvent(on_ws_event);
}

static void update_led(uint32_t now) {
  bool on;
  if (g_ctrl.armed()) {
    on = true;  // solid
  } else if (g_ctrl.killed() && g_client >= 0) {
    on = (now / 100) % 2;  // 5 Hz: KILL latched or calibrating
  } else if (g_ctrl.calibrating()) {
    on = (now / 100) % 2;
  } else if (g_client >= 0) {
    on = (now / 500) % 2;  // 1 Hz: phone connected, disarmed
  } else {
    on = false;  // no phone
  }
  digitalWrite(kLedPin, on ? HIGH : LOW);
}

void setup() {
  Serial.begin(115200);
  pinMode(kLedPin, OUTPUT);
  g_arm.begin();
  g_kill.begin();
  start_wifi_and_radio();
  start_servers();
  Serial.printf("mobula7_tx: Wi-Fi \"%s\", open http://%s\n", kSsid,
                WiFi.softAPIP().toString().c_str());
}

void loop() {
  static uint32_t last_send = 0, last_status = 0, last_log = 0;
  static uint16_t seq = 0;

  g_http.handleClient();
  g_ws.loop();

  uint32_t now = millis();
  g_arm.update(now);
  g_kill.update(now);

  if ((uint32_t)(now - last_send) >= kSendPeriodMs) {
    last_send = now;
    m7::TxInputs in = {};
    in.now_ms = now;
    in.arm_btn = g_arm.pressed;
    in.kill_btn = g_kill.pressed;
    in.phone_connected = g_client >= 0;
    in.last_phone_ms = g_last_phone_ms;
    in.roll = g_sticks.roll;
    in.pitch = g_sticks.pitch;
    in.throttle = g_sticks.throttle;
    in.yaw = g_sticks.yaw;
    in.beep = g_sticks.beep;
    in.calib_request = g_calib_request;
    g_calib_request = false;
    g_ctrl.update(in);

    m7::LinkPacket p = {};
    p.seq = seq++;
    uint16_t ch[m7::kNumChannels];
    g_ctrl.channels(ch);
    memcpy(p.ch, ch, sizeof(ch));
    m7::packet_seal(p);
    esp_now_send(kBroadcast, (const uint8_t*)&p, sizeof(p));
  }

  if ((uint32_t)(now - last_status) >= kStatusPeriodMs && g_client >= 0) {
    last_status = now;
    char buf[16];
    if (m7::format_status(buf, sizeof(buf), g_ctrl.armed(), g_ctrl.killed(),
                          g_ctrl.calibrating()) > 0) {
      g_ws.sendTXT((uint8_t)g_client, buf);
    }
  }

  update_led(now);

  if ((uint32_t)(now - last_log) >= 1000) {
    last_log = now;
    uint16_t ch[m7::kNumChannels];
    g_ctrl.channels(ch);
    Serial.printf("phone=%d arm_btn=%d kill_btn=%d armed=%d killed=%d calib=%d thr=%u roll=%u\n",
                  g_ctrl.phone_alive() ? 1 : 0, g_arm.pressed ? 1 : 0,
                  g_kill.pressed ? 1 : 0, g_ctrl.armed() ? 1 : 0,
                  g_ctrl.killed() ? 1 : 0, g_ctrl.calibrating() ? 1 : 0,
                  ch[m7::CH_THROTTLE], ch[m7::CH_ROLL]);
  }
}
