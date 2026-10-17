// Mobula7 drone-side receiver: ESP-NOW from the remote -> iBUS to Betaflight.
//
// Wiring (see mobula7-remote/README.md):
//   D17 (GPIO17, TX2) -> Crazybee pad R2
//   GND               -> Crazybee battery minus
//   VIN               -> Crazybee battery plus (only when NOT on USB)
//
// Requires the esp32 Arduino core 3.x and the Mobula7Link library.

// 1 = ignore the radio and sweep the Roll channel slowly (bench test, step 2).
// 0 = normal operation.
#define RX_SELFTEST 1

#include <Mobula7Link.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

static const int kIbusTxPin = 17;
static const int kIbusRxPin = 16;  // unused, Serial2 needs one
static const int kLedPin = 2;
static const uint32_t kFramePeriodMs = 7;

static m7::RxLink g_link;

static portMUX_TYPE g_mux = portMUX_INITIALIZER_UNLOCKED;
static m7::LinkPacket g_pending;
static uint32_t g_pending_ms = 0;
static volatile bool g_has_pending = false;

static void on_recv(const esp_now_recv_info_t*, const uint8_t* data, int len) {
  m7::LinkPacket p;
  if (!m7::packet_parse(data, len, &p)) return;
  uint32_t now = millis();
  portENTER_CRITICAL(&g_mux);
  g_pending = p;
  g_pending_ms = now;
  g_has_pending = true;
  portEXIT_CRITICAL(&g_mux);
}

static void start_radio() {
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(m7::kWifiChannel, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);
  if (esp_now_init() != ESP_OK) {
    Serial.println("esp_now_init failed");
    return;
  }
  esp_now_register_recv_cb(on_recv);
}

static void selftest_channels(uint32_t now, uint16_t out[m7::kNumChannels]) {
  m7::safe_channels(out);
  uint32_t phase = now % 4000;  // 1000 -> 2000 -> 1000 over 4 s
  uint32_t v = phase < 2000 ? phase / 2 : (4000 - phase) / 2;
  out[m7::CH_ROLL] = (uint16_t)(1000 + v);
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, kIbusRxPin, kIbusTxPin);
  pinMode(kLedPin, OUTPUT);
#if !RX_SELFTEST
  start_radio();
#endif
  Serial.println(RX_SELFTEST ? "mobula7_rx: SELFTEST" : "mobula7_rx: ready");
}

void loop() {
  static uint32_t last_frame = 0, last_log = 0, last_blink = 0;
  static bool led = false;
  uint32_t now = millis();
  if ((uint32_t)(now - last_frame) < kFramePeriodMs) return;
  last_frame = now;

  uint16_t ch[m7::kNumChannels];
  bool ok;
#if RX_SELFTEST
  selftest_channels(now, ch);
  ok = true;
#else
  if (g_has_pending) {
    m7::LinkPacket p;
    uint32_t t;
    portENTER_CRITICAL(&g_mux);
    p = g_pending;
    t = g_pending_ms;
    g_has_pending = false;
    portEXIT_CRITICAL(&g_mux);
    g_link.on_packet(p, t);
  }
  g_link.output(now, ch);
  ok = g_link.link_ok(now);
#endif

  uint8_t frame[m7::kIbusFrameLen];
  m7::ibus_build_frame(ch, frame);
  Serial2.write(frame, sizeof(frame));

  // LED: solid = link ok, fast blink = no link.
  if (ok) {
    led = true;
  } else if ((uint32_t)(now - last_blink) >= 100) {
    last_blink = now;
    led = !led;
  }
  digitalWrite(kLedPin, led ? HIGH : LOW);

  if ((uint32_t)(now - last_log) >= 1000) {
    last_log = now;
    Serial.printf("link=%d arm=%u thr=%u roll=%u\n", ok ? 1 : 0, ch[m7::CH_ARM],
                  ch[m7::CH_THROTTLE], ch[m7::CH_ROLL]);
  }
}
