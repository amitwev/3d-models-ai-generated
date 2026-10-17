# Mobula7 ESP32 Remote — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two ESP32 firmwares and an iPhone control page. With them, a phone's on-screen sticks fly a Betaflight Mobula7 over ESP-NOW and iBUS, and every kill or link-loss path disarms the drone immediately.

**Architecture:** Safety-critical logic lives in a header-only, Arduino-free C++ library, `Mobula7Link`, which covers iBUS framing, the radio packet, the TX arming state machine, the RX link-loss latch and the phone message protocol. It is unit-tested on the host with g++.

Two thin Arduino sketches wire that library to the hardware:
- **TX:** Wi-Fi AP, HTTP and WebSocket, buttons, and ESP-NOW broadcast.
- **RX:** ESP-NOW receive and UART iBUS output.

The phone page is one self-contained HTML file. A script embeds it into a C header for the TX sketch, and it is tested in headless Chromium with a mocked WebSocket.

**Tech Stack:**
- C++17 (host tests: g++ `-Wall -Wextra -Werror`).
- Arduino IDE 2 with Espressif esp32 core **3.x**. Its ESP-NOW receive callback takes `const esp_now_recv_info_t*`.
- One external Arduino library: **WebSockets by Markus Sattler** (`WebSocketsServer.h`).
- Vanilla HTML, CSS and JS for the page.
- Python 3 for the embed script.
- Node and Playwright for the page tests. Chromium is preinstalled; launch it with `executablePath: '/opt/pw-browsers/chromium'` if the default lookup fails.

**Spec:** `docs/superpowers/specs/2026-10-16-mobula7-esp32-remote-phase1-design.md`. Read the sections "התנהגות: ערוצים, חימוש וכיבוי", "תקשורת", "דף השליטה" and "Betaflight: בלוק CLI".

## Global Constraints

- **Channel order:** AETR. iBUS has 14 channels, with values 1000–2000.
  - CH1 Roll, CH2 Pitch, CH3 Throttle, CH4 Yaw.
  - CH5 AUX1 = ARM (2000 when armed, 1000 otherwise).
  - CH6 AUX2 = ANGLE (always 1000).
  - CH7 AUX3 = BEEPER (2000 while BEEP is pressed).
  - CH8–14 = 1500.
- **Arming** happens only from the physical ARM button, never from the page. The button must be held **500 ms** with throttle **< 1050**, the phone alive, and KILL not pressed. After any disarm, ARM must be released and pressed again.
- **Kill paths:**
  - KILL button → immediate disarm.
  - No phone message for **> 300 ms** → same as KILL.
  - RX with no valid packet for **> 150 ms** → keeps sending valid iBUS with throttle 1000 and AUX1 1000.
  - After link loss, RX forces AUX1 = 1000 until it receives a packet whose AUX1 is 1000.
- **Accel calibration:** only while disarmed. For **2000 ms** send throttle 2000, yaw 1000, pitch 1000, roll 1500 and AUX1 1000.
- **ESP-NOW:** broadcast at about **50 Hz** on a fixed Wi-Fi channel shared by the TX AP and the RX.
- **RX output:** iBUS on UART2 at 115200 8N1, TX pin **GPIO17**, one frame every **7 ms**.
- **TX pins:** ARM on **GPIO25**, KILL on **GPIO26**, both wired to GND with internal pull-up (active low). The status LED is **GPIO2**.
- **Phone page:** served at `http://192.168.4.1`. It uses no external resources, works in landscape, supports multitouch, and blocks scroll, zoom and selection. The left stick is throttle (does not recenter) and yaw (recenters). The right stick is roll and pitch (both recenter). Mode 2.
- **Language:** all user-facing text (page and README) is Hebrew in plain language. Code identifiers and comments are English.
- **Location:** all code goes under `mobula7-remote/firmware/`.
- **Betaflight:** the target firmware is 2026.6.2. The CLI block in the spec is the delivered config.

## Review Focus

1. **Phone locked or Safari backgrounded mid-flight.** The socket may stay "connected" while messages stop, and the TX must still kill within 300 ms. Covered by a `TxController` test: connected but stale `last_phone_ms` → killed.
2. **TX reboots or loses power while armed, then comes back still sending AUX1 = 2000** (for example from stale state). The RX must not re-arm. Covered by an `RxLink` test.
3. **ARM held through KILL or through power-up.** Releasing KILL while ARM is still held must not arm. Covered by a `TxController` test.
4. **Foreign or garbage ESP-NOW traffic on the same channel** (wrong length, magic, version or CRC) is ignored. Covered by `packet_parse` tests.
5. **Malformed or out-of-range page messages** (`S,5000,…`, truncated, non-numeric) must never pass a value outside 1000–2000. Covered by `parse_stick_msg` tests.
6. **`millis()` wraparound** near `UINT32_MAX` must not trigger, or hide, a timeout. Covered by an `RxLink` test.

---

## File Map

```
mobula7-remote/firmware/
  Mobula7Link/                     Arduino library (header-only, no Arduino deps)
    library.properties
    src/Mobula7Link.h              umbrella include
    src/link_config.h              constants + channel indexes
    src/ibus.h                     iBUS frame builder
    src/link_packet.h              radio packet + CRC
    src/rx_link.h                  RxLink: packet → safe channel output
    src/tx_controller.h            TxController: buttons/phone → channels
    src/ws_protocol.h              phone message parse/format
  tests/
    check.h                        tiny assert macros
    test_main.cpp                  runs all tests
    test_ibus.cpp test_packet.cpp test_rx_link.cpp test_tx_controller.cpp test_ws_protocol.cpp
    Makefile                       `make test`
  web/
    control.html                   phone page (source of truth)
    tests/control_test.mjs         Playwright, mocked WebSocket
  tools/embed_page.py              control.html → mobula7_tx/control_page.h (+ --check)
  mobula7_rx/mobula7_rx.ino
  mobula7_tx/mobula7_tx.ino
  mobula7_tx/control_page.h        generated
mobula7-remote/README.md           Hebrew setup + flashing guide
mobula7-remote/phase1-guide.html   update steps 2–3 to match
```

---

### Task 1: Library scaffold, config and iBUS frame

**Files:**
- Create: `Mobula7Link/library.properties`, `src/Mobula7Link.h`, `src/link_config.h`, `src/ibus.h`
- Create: `tests/check.h`, `tests/test_main.cpp`, `tests/test_ibus.cpp`, `tests/Makefile`

**Interfaces:**
- Produces, in `link_config.h` (namespace `m7`):
  - `constexpr int kNumChannels = 14;`
  - `kChLow = 1000`, `kChMid = 1500`, `kChHigh = 2000` (`uint16_t`).
  - Channel indexes: `CH_ROLL=0, CH_PITCH=1, CH_THROTTLE=2, CH_YAW=3, CH_ARM=4, CH_ANGLE=5, CH_BEEPER=6`.
  - `constexpr uint8_t kWifiChannel = 6;`
  - Timing (`uint32_t`): `kRxLinkTimeoutMs=150`, `kPhoneTimeoutMs=300`, `kArmHoldMs=500`, `kCalibDurationMs=2000`.
  - `constexpr uint16_t kArmThrottleMax = 1050;`
  - `inline uint16_t clamp_ch(int v)` clamps to 1000..2000.
- Produces, in `ibus.h`: `constexpr int kIbusFrameLen = 32; void ibus_build_frame(const uint16_t ch[kNumChannels], uint8_t out[kIbusFrameLen]);`
- Test harness: `check.h` defines `CHECK(cond)` and `CHECK_EQ(a,b)`. Both print file:line on failure and increment a global failure count. `test_main.cpp` calls each `run_*_tests()` and returns non-zero on any failure.

- [ ] **Step 1: Write failing tests in `test_ibus.cpp` (`run_ibus_tests()`)**

```cpp
uint16_t ch[14]; for (auto& c : ch) c = 1500; ch[2] = 1000;
uint8_t f[32]; m7::ibus_build_frame(ch, f);
CHECK_EQ(f[0], 0x20); CHECK_EQ(f[1], 0x40);
CHECK_EQ(f[2] | (f[3] << 8), 1500);          // CH1 little-endian
CHECK_EQ(f[6] | (f[7] << 8), 1000);          // CH3
uint16_t sum = 0xFFFF; for (int i = 0; i < 30; i++) sum -= f[i];
CHECK_EQ(f[30] | (f[31] << 8), sum);         // checksum = 0xFFFF - sum(bytes 0..29)
ch[0] = 2500; ch[1] = 10; m7::ibus_build_frame(ch, f);
CHECK_EQ(f[2] | (f[3] << 8), 2000);          // clamped high
CHECK_EQ(f[4] | (f[5] << 8), 1000);          // clamped low
```

- [ ] **Step 2: Write `tests/Makefile`**

Target `test`: `g++ -std=c++17 -Wall -Wextra -Werror -I../Mobula7Link/src *.cpp -o build/tests && ./build/tests`. Run it: compile FAIL (headers missing).

- [ ] **Step 3: Implement the headers and `library.properties`**

`library.properties` fields: `name=Mobula7Link`, `version=0.1.0`, `architectures=*`, `includes=Mobula7Link.h`. The headers include only `<stdint.h>`, `<stddef.h>` and `<string.h>`.

- [ ] **Step 4: Run `make -C mobula7-remote/firmware/tests test`**

Expected: `all tests passed`, exit 0.

- [ ] **Step 5: Commit** `feat(mobula7): Mobula7Link scaffold and iBUS frame builder`

---

### Task 2: Radio packet

**Files:** Create `src/link_packet.h`, `tests/test_packet.cpp`

**Interfaces:**
- Produces:
  ```cpp
  struct __attribute__((packed)) LinkPacket {
    uint32_t magic;    // kPacketMagic = 0x4D375258 ('M7RX')
    uint8_t  version;  // kPacketVersion = 1
    uint8_t  flags;    // 0, reserved
    uint16_t seq;
    uint16_t ch[kNumChannels];
    uint16_t crc;      // CRC-16/CCITT-FALSE over all preceding bytes
  };
  ```
- Produces functions:
  - `uint16_t crc16_ccitt(const uint8_t* d, size_t n);` (poly 0x1021, init 0xFFFF)
  - `void packet_seal(LinkPacket& p);` sets magic, version and crc. Channels and seq are set by the caller.
  - `bool packet_parse(const uint8_t* data, int len, LinkPacket* out);` returns true only if `len == sizeof(LinkPacket)` and magic, version and crc all match. It copies into `out`.

- [ ] **Step 1: Failing tests (`run_packet_tests()`)**
  - `crc16_ccitt("123456789", 9) == 0x29B1`.
  - A sealed packet round-trips through `packet_parse` with an identical `ch` and `seq`.
  - Each of these returns false: length − 1; length + 1; `magic` changed; `version = 2`; one channel byte flipped after sealing; `len = 0`.
- [ ] **Step 2: Run, expect failure** (`make test`).
- [ ] **Step 3: Implement.** Add `static_assert(sizeof(LinkPacket) == 38)`.
- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** `feat(mobula7): ESP-NOW link packet with CRC`

---

### Task 3: RxLink — safe output on the drone side

**Files:** Create `src/rx_link.h`, `tests/test_rx_link.cpp`

**Interfaces:**
- Consumes: `LinkPacket`, constants (Tasks 1–2).
- Produces:
  ```cpp
  class RxLink {
   public:
    void on_packet(const LinkPacket& p, uint32_t now_ms);
    void output(uint32_t now_ms, uint16_t out[kNumChannels]) const;
    bool link_ok(uint32_t now_ms) const;   // a packet was received within kRxLinkTimeoutMs
  };
  void safe_channels(uint16_t out[kNumChannels]);  // roll/pitch/yaw 1500, throttle 1000, ARM/ANGLE/BEEPER 1000, CH8–14 1500
  ```
- **Behavior:**
  - Starts latched: no packet has been received yet, and the "must see disarm" latch is set.
  - When `!link_ok`, the output is `safe_channels`, and the latch is set again.
  - When `link_ok`, the output is the last packet's channels, each passed through `clamp_ch`. While the latch is set, `out[CH_ARM]` is forced to 1000.
  - The latch clears when a packet arrives with `ch[CH_ARM] < 1500`.
  - All time comparisons use `uint32_t` subtraction: `now - last <= kRxLinkTimeoutMs`.

- [ ] **Step 1: Failing tests (`run_rx_link_tests()`)**
  - A new RxLink at `now = 0` outputs `safe_channels`.
  - Packet with ARM 2000 and throttle 1400 at t=0 → output ARM 1000 (latched), throttle 1400.
  - Then packet with ARM 1000 at t=10 → latch clears. Then packet with ARM 2000 at t=20 → output ARM 2000.
  - Armed packet at t=20; `output(t=171)` → `safe_channels` (151 ms > 150). `output(t=170)` → still the packet.
  - After that loss, a new packet with ARM 2000 at t=300 → ARM stays 1000, i.e. latched (Review Focus #2).
  - Wraparound: packets at `now = 0xFFFFFFF0`, then `output(0x00000010)`, a 32 ms gap → link ok. `output(0x000000A0)`, a 176 ms gap → safe.
  - Packet with channel value 2600 → output 2000.
- [ ] **Step 2: Run, expect failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** `feat(mobula7): RxLink link-loss disarm and re-arm latch`

---

### Task 4: TxController — arming, kill, beep and calibration

**Files:** Create `src/tx_controller.h`, `tests/test_tx_controller.cpp`

**Interfaces:**
- Consumes: constants (Task 1).
- Produces:
  ```cpp
  struct TxInputs {
    uint32_t now_ms;
    bool arm_btn, kill_btn;        // true = pressed (already debounced)
    bool phone_connected;          // a WebSocket client exists
    uint32_t last_phone_ms;        // time of last valid stick message
    uint16_t roll, pitch, throttle, yaw;   // last stick values from phone
    bool beep;                     // BEEP held on page
    bool calib_request;            // edge: page pressed "כיול אופק" this cycle
  };
  class TxController {
   public:
    void update(const TxInputs& in);
    void channels(uint16_t out[kNumChannels]) const;
    bool armed() const;
    bool killed() const;           // kill latch active
    bool calibrating() const;
    bool phone_alive() const;      // connected && now - last_phone_ms <= kPhoneTimeoutMs
  };
  ```
- **Rules (copied from Global Constraints):**
  - `kill_btn` or `!phone_alive` → disarm, set the kill latch and cancel calibration.
  - The kill latch clears when `kill_btn` is released, the phone is alive and `arm_btn` is released.
  - Arm when `arm_btn` has been continuously held ≥ 500 ms, and the press began after the latch cleared, with throttle < 1050, the phone alive, no kill, and not calibrating.
  - ARM pressed while already armed does nothing.
- **Channel output:**
  - Kill latched or phone not alive → `safe_channels`.
  - Calibrating → throttle 2000, yaw 1000, pitch 1000, roll 1500, ARM 1000.
  - Otherwise the sticks pass through (clamped). ARM is 2000 when armed. ANGLE is always 1000. BEEPER is 2000 when `beep` and the phone is alive.
- **Calibration:** starts on `calib_request` only when disarmed, the phone is alive and there is no kill. It lasts 2000 ms.

- [ ] **Step 1: Failing tests (`run_tx_controller_tests()`).** Use a helper `alive(t)` that returns inputs with `phone_connected = true`, `last_phone_ms = t` and throttle 1000.
  - ARM held from t=0: at t=499 not armed, at t=500 armed, and `channels()[CH_ARM] == 2000`.
  - ARM held with throttle 1100 for 1 s → not armed.
  - Armed, then `kill_btn` → not armed, `killed()`, throttle 1000.
  - ARM held through KILL: press ARM, then KILL, release KILL while still holding ARM for 2 s → not armed. Release ARM and hold again for 500 ms → armed (Review Focus #3).
  - Armed with `phone_connected = true` but `last_phone_ms` 301 ms old → killed (Review Focus #1). At 300 ms old → still armed.
  - Power-up with ARM already held (first update has `arm_btn = true`) and held 2 s → not armed.
  - Disarmed with `calib_request` → `calibrating()`. Channels are throttle 2000, yaw 1000, pitch 1000, ARM 1000. At t + 2000 it is no longer calibrating.
  - `calib_request` while armed → ignored.
  - ARM held during calibration → not armed.
  - `beep` true → BEEPER 2000. Phone stale → BEEPER 1000.
  - ANGLE is 1000 in every case above.
- [ ] **Step 2: Run, expect failure.**
- [ ] **Step 3: Implement.** Track `arm_press_start_ms` and an `arm_press_valid` flag. A press is valid only if it began while no latch was active.
- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** `feat(mobula7): TxController arming, kill latch, calibration`

---

### Task 5: Phone message protocol

**Files:** Create `src/ws_protocol.h`, `tests/test_ws_protocol.cpp`

**Interfaces:**
- Produces:
  ```cpp
  struct StickMsg { uint16_t roll, pitch, throttle, yaw; bool beep, calib; };
  // Phone → TX text frame: "S,<roll>,<pitch>,<throttle>,<yaw>,<beep 0|1>,<calib 0|1>"
  bool parse_stick_msg(const char* s, size_t len, StickMsg* out);
  // TX → phone text frame: "T,<armed>,<killed>,<calibrating>"  e.g. "T,0,1,0"
  int format_status(char* buf, size_t n, bool armed, bool killed, bool calibrating);
  ```
- `parse_stick_msg` returns false unless the message has exactly 7 fields: a leading `S` and six base-10 integers, without trailing characters. The four stick values must be in 0..9999 and are passed through `clamp_ch`. `beep` and `calib` must be exactly 0 or 1. `len` bounds the read, and the string need not be NUL-terminated.

- [ ] **Step 1: Failing tests (`run_ws_protocol_tests()`)**
  - `"S,1500,1600,1000,1400,0,1"` parses to roll 1500, pitch 1600, throttle 1000, yaw 1400, beep false, calib true.
  - `"S,5000,1500,1000,1500,0,0"` gives roll 2000. `"S,0,…"` gives 1000.
  - Each of these is rejected: `"S,1500,1500,1000,1500,0"` (6 fields), `"S,1500,1500,1000,1500,0,0,9"`, `"X,1500,…"`, `"S,15a0,…"`, `"S,1500,1500,1000,1500,2,0"`, `""`, and a valid string with `len` cut mid-number.
  - `format_status(buf, 16, true, false, false)` gives `"T,1,0,0"` and returns 7. When `n` is too small it returns −1.
- [ ] **Step 2: Run, expect failure.**
- [ ] **Step 3: Implement.** No `sscanf`. Use a manual digit loop.
- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** `feat(mobula7): phone stick/status message protocol`

---

### Task 6: RX sketch

**Files:** Create `mobula7_rx/mobula7_rx.ino`

**Interfaces:**
- Consumes: `RxLink`, `packet_parse`, `ibus_build_frame`, `kWifiChannel`.
- **Hardware:**
  - `Serial2.begin(115200, SERIAL_8N1, 16, 17)`.
  - Wi-Fi in `WIFI_STA`, then `esp_wifi_set_channel(kWifiChannel, WIFI_SECOND_CHAN_NONE)` and `esp_now_init()`.
  - The receive callback uses the core 3.x signature `void on_recv(const esp_now_recv_info_t*, const uint8_t*, int)`. It calls `packet_parse` and, on success, copies the packet and `millis()` under a `portMUX` critical section.
- **Loop:**
  - Every 7 ms, feed any pending packet to `RxLink`. Then call `output(millis())`, `ibus_build_frame` and `Serial2.write`.
  - LED on GPIO2: solid while `link_ok`, toggling every 100 ms otherwise.
  - `Serial` at 115200 logs one line per second: `link=<0|1> arm=<ch5> thr=<ch3>`.
- **Self-test mode for guide step 2:** `#define RX_SELFTEST 0` at the top of the file. When it is 1, ESP-NOW is ignored. Roll sweeps 1000→2000→1000 over 4 s, the other sticks stay at 1500, throttle and ARM stay at 1000, and ANGLE stays at 1000.

- [ ] **Step 1: Write the sketch.**
- [ ] **Step 2: Host sanity:** `make test` still passes. Compile check is in Task 9.
- [ ] **Step 3: Commit** `feat(mobula7): RX firmware (ESP-NOW → iBUS)`

---

### Task 7: Phone control page and embed tool

**Files:** Create `web/control.html`, `web/tests/control_test.mjs`, `tools/embed_page.py`, `mobula7_tx/control_page.h` (generated)

**Interfaces:**
- **Consumes:** the protocol from Task 5. The page connects to `ws://${location.hostname}:81/`. A test can override the URL with `?ws=<url>`.
- **Produces:**
  - `embed_page.py` writes `static const char CONTROL_PAGE[] PROGMEM = R"M7PAGE(...)M7PAGE";`.
  - `embed_page.py --check` exits 1 if the header is stale.
  - The page exposes `window.__m7 = { sticks }` for tests only. `sticks` holds the current values.
- **Page behavior:**
  - `dir="rtl"`, Hebrew labels, landscape layout with two stick pads. No external resources.
  - `touch-action: none`, `user-select: none`, and a viewport with `user-scalable=no`.
  - Pointer Events with per-pointer tracking, so two thumbs work at once.
  - The left pad's vertical axis is throttle: bottom 1000, top 2000, and it keeps its value on release. Its horizontal axis is yaw and recenters to 1500 on release.
  - The right pad is roll (horizontal) and pitch (vertical, up = 2000). Both recenter.
  - Sends `S,…` every 20 ms while the socket is open. On `visibilitychange` to hidden it closes the socket, and it reconnects when visible again.
  - "BEEP" button: hold to beep (sends `beep=1` while held).
  - "כיול אופק" button: sends `calib=1` in one message. It is disabled while armed.
  - Status bar from the latest `T,…` message:
    - "חמוש" in red when armed.
    - "נעול – לחץ ARM בשלט" when disarmed.
    - "KILL – שחרר ושוב ARM" when killed.
    - "מכייל – הרחפן על משטח ישר" while calibrating.
    - "אין קשר לשלט" when no message arrived for 1 s.
  - No arm button on the page.

- [ ] **Step 1: Write the failing Playwright test `control_test.mjs`.** Use a plain node script with `assert`. Before load, an init script replaces `window.WebSocket` with a fake that records sent strings and exposes `__fakeWs.receive(text)`. Assertions:
  - Within 100 ms, a message matching `/^S,1500,1500,1000,1500,0,0$/` is sent.
  - Pointer drag on the left pad from center to top → the last message has throttle ≥ 1950. After pointerup, throttle is still ≥ 1950 and yaw is 1500.
  - Right pad: pointerdown at the right edge with `pointerId 2`, while `pointerId 1` holds the left pad → roll ≥ 1950 and throttle unchanged. After pointerup, roll is 1500.
  - Click "כיול אופק" → exactly one message has calib 1, and the following messages have calib 0.
  - `__fakeWs.receive("T,1,0,0")` → the status text contains "חמוש" and the calibrate button is disabled.
  - No message for 1100 ms → the status contains "אין קשר".
  - The page makes no network requests other than the document itself (checked via `page.on('request')`).
- [ ] **Step 2: Run** `node mobula7-remote/firmware/web/tests/control_test.mjs`. Expect FAIL (no page).
- [ ] **Step 3: Implement `control.html` and `embed_page.py`, then run the embed.**
- [ ] **Step 4: Run the test (expect PASS) and `python3 tools/embed_page.py --check` (expect exit 0).**
- [ ] **Step 5: Commit** `feat(mobula7): phone control page + embed tool`

---

### Task 8: TX sketch

**Files:** Create `mobula7_tx/mobula7_tx.ino`

**Interfaces:**
- Consumes: `TxController`, `TxInputs`, `parse_stick_msg`, `format_status`, `LinkPacket`, `packet_seal`, `CONTROL_PAGE`.
- **Wi-Fi:**
  - `WiFi.mode(WIFI_AP_STA)`.
  - `WiFi.softAP("Mobula7-Remote", "mobula7fly", kWifiChannel)`. The AP IP stays at the default 192.168.4.1.
  - `esp_now_init()`, then add the broadcast peer `FF:FF:FF:FF:FF:FF` with `channel = kWifiChannel` and `ifidx = WIFI_IF_AP`.
- **Servers:**
  - `WebServer` on port 80. `/` serves `CONTROL_PAGE` as `text/html; charset=utf-8`, and every other path redirects to `/`.
  - `WebSocketsServer` on port 81.
  - Text frames go through `parse_stick_msg`. On success they update the stick state and `last_phone_ms = millis()`, and `calib` becomes a one-shot `calib_request`.
  - Only the most recent client is kept: on a new connect, disconnect older ones.
- **Buttons:** `INPUT_PULLUP` on 25 and 26, active low, 20 ms debounce.
- **Loop:**
  - `server.handleClient()` and `ws.loop()`.
  - Every 20 ms: build `TxInputs`, call `update`, fill a `LinkPacket` with `channels()` and an incrementing seq, `packet_seal`, then `esp_now_send` to broadcast.
  - Every 200 ms: `broadcastTXT` the `format_status` string.
- **LED on GPIO2:**
  - Off: no phone.
  - 1 Hz blink: phone connected, disarmed.
  - Solid: armed.
  - 5 Hz blink: killed or calibrating.

- [ ] **Step 1: Write the sketch.**
- [ ] **Step 2: Host sanity:** `make test` and the page test pass.
- [ ] **Step 3: Commit** `feat(mobula7): TX firmware (AP + WebSocket + ESP-NOW)`

---

### Task 9: Compile check, Hebrew README and guide update

**Files:** Create `mobula7-remote/README.md`. Modify `mobula7-remote/phase1-guide.html` (steps 2–3 and the wiring tips).

- [ ] **Step 1: Best-effort compile check.**
  - Download `arduino-cli` from GitHub releases. That host is reachable here; downloads.arduino.cc and espressif.github.io are blocked.
  - Try the esp32 core index via `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`.
  - If the core and WebSockets library install, run `arduino-cli compile --fqbn esp32:esp32:esp32 --library firmware/Mobula7Link` for both sketches, and the TX compile also gets the WebSockets library. Expected: both compile.
  - If the toolchain cannot be fetched, record that in the final report as "not compiled for ESP32 in this environment". Do not mark it as passed.
- [ ] **Step 2: Write `README.md` in Hebrew, plain language:**
  1. Install Arduino IDE 2.
  2. Add the esp32 core under Boards Manager (URL `https://espressif.github.io/arduino-esp32/package_esp32_index.json`), version 3.x.
  3. Install the "WebSockets" library by Markus Sattler from Library Manager.
  4. Install Mobula7Link: copy `firmware/Mobula7Link` into `~/Documents/Arduino/libraries/`.
  5. Board: "ESP32 Dev Module". Pick the port and Upload. If the upload hangs on "Connecting…", hold BOOT on the ESP32.
  6. Flash `mobula7_rx` to the board that goes on the drone, first with `RX_SELFTEST 1` for guide step 2, then with 0. Flash `mobula7_tx` to the remote board.
  7. Wiring tables for RX and TX, copied from the spec, including the warning not to use `3V3` or `VN`.
  8. Phone: connect Wi-Fi to `Mobula7-Remote`, password `mobula7fly`, and open `http://192.168.4.1`. If iOS asks, choose "use without internet".
  9. The Betaflight CLI block from the spec.
  10. A LED meaning table for both boards.
- [ ] **Step 3: Update `phase1-guide.html`:**
  - Step 2 items point to `RX_SELFTEST 1`, D17→R2, the CLI block, and seeing Roll sweep in the Receiver tab.
  - Step 3 items: Wi-Fi name and password, URL, ARM on D25 and KILL on D26.
  - The "פקודת Betaflight" section uses the spec's final CLI block.
  - Republish the artifact at the same path.
- [ ] **Step 4: Final verification:** `make test`, the page test, and `embed_page.py --check` all pass.
- [ ] **Step 5: Commit and push** `docs(mobula7): flashing guide and phase-1 guide update`
