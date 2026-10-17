#include "check.h"
#include "Mobula7Link.h"

using namespace m7;

// Inputs for a live phone at time t, throttle low, nothing pressed.
static TxInputs alive(uint32_t t) {
  TxInputs in{};
  in.now_ms = t;
  in.phone_connected = true;
  in.last_phone_ms = t;
  in.roll = in.pitch = in.yaw = kChMid;
  in.throttle = kChLow;
  return in;
}

static uint16_t ch(const TxController& c, int idx) {
  uint16_t out[kNumChannels];
  c.channels(out);
  return out[idx];
}

// Feed `in` every 10 ms from in.now_ms up to and including `until`.
static void run_until(TxController& c, TxInputs in, uint32_t until) {
  for (uint32_t t = in.now_ms; t <= until; t += 10) {
    in.now_ms = t;
    in.last_phone_ms = t;
    c.update(in);
  }
}

void run_tx_controller_tests() {
  // Hold ARM 500 ms with throttle low -> armed.
  {
    TxController c;
    run_until(c, alive(0), 100);  // phone up, nothing pressed: latch clears
    TxInputs in = alive(110);
    in.arm_btn = true;
    run_until(c, in, 600);
    CHECK(!c.armed());  // held 490 ms
    in.now_ms = 610;
    in.last_phone_ms = 610;
    c.update(in);
    CHECK(c.armed());  // held 500 ms
    CHECK_EQ(ch(c, CH_ARM), 2000);
    CHECK_EQ(ch(c, CH_ANGLE), 1000);
  }

  // Throttle above 1050 blocks arming.
  {
    TxController c;
    run_until(c, alive(0), 100);
    TxInputs in = alive(110);
    in.arm_btn = true;
    in.throttle = 1100;
    run_until(c, in, 1200);
    CHECK(!c.armed());
    CHECK_EQ(ch(c, CH_ARM), 1000);
  }

  // KILL disarms immediately and latches.
  {
    TxController c;
    run_until(c, alive(0), 100);
    TxInputs in = alive(110);
    in.arm_btn = true;
    run_until(c, in, 700);
    CHECK(c.armed());
    in = alive(710);
    in.throttle = 1400;
    c.update(in);
    CHECK_EQ(ch(c, CH_THROTTLE), 1400);
    in.now_ms = in.last_phone_ms = 720;
    in.kill_btn = true;
    c.update(in);
    CHECK(!c.armed());
    CHECK(c.killed());
    CHECK_EQ(ch(c, CH_THROTTLE), 1000);
    CHECK_EQ(ch(c, CH_ARM), 1000);
  }

  // ARM held through KILL: no re-arm until ARM is released and pressed again.
  {
    TxController c;
    run_until(c, alive(0), 100);
    TxInputs in = alive(110);
    in.arm_btn = true;
    run_until(c, in, 700);
    CHECK(c.armed());
    in.kill_btn = true;
    run_until(c, in, 800);
    in.kill_btn = false;
    run_until(c, in, 2800);  // ARM still held for 2 s after KILL released
    CHECK(!c.armed());
    in.arm_btn = false;
    run_until(c, in, 2900);
    in.arm_btn = true;
    in.now_ms = 2910;
    run_until(c, in, 3410);
    CHECK(c.armed());
  }

  // Stale phone (socket open but silent > 300 ms) kills; 300 ms is still ok.
  {
    TxController c;
    run_until(c, alive(0), 100);
    TxInputs in = alive(110);
    in.arm_btn = true;
    run_until(c, in, 700);
    CHECK(c.armed());
    in.arm_btn = false;
    in.last_phone_ms = 700;
    in.now_ms = 1000;  // 300 ms old
    c.update(in);
    CHECK(c.armed());
    in.now_ms = 1001;  // 301 ms old
    c.update(in);
    CHECK(!c.armed());
    CHECK(c.killed());
    CHECK(!c.phone_alive());
  }

  // Power-up with ARM already held never arms.
  {
    TxController c;
    TxInputs in = alive(0);
    in.arm_btn = true;
    run_until(c, in, 2000);
    CHECK(!c.armed());
  }

  // No phone at all: safe output.
  {
    TxController c;
    TxInputs in{};
    in.now_ms = 50;
    in.throttle = 1800;
    c.update(in);
    CHECK_EQ(ch(c, CH_THROTTLE), 1000);
    CHECK_EQ(ch(c, CH_ROLL), 1500);
  }

  // Accelerometer calibration: only while disarmed, for 2000 ms.
  {
    TxController c;
    run_until(c, alive(0), 100);
    TxInputs in = alive(110);
    in.calib_request = true;
    c.update(in);
    CHECK(c.calibrating());
    CHECK_EQ(ch(c, CH_THROTTLE), 2000);
    CHECK_EQ(ch(c, CH_YAW), 1000);
    CHECK_EQ(ch(c, CH_PITCH), 1000);
    CHECK_EQ(ch(c, CH_ROLL), 1500);
    CHECK_EQ(ch(c, CH_ARM), 1000);
    // ARM held during calibration does not arm.
    in.calib_request = false;
    in.arm_btn = true;
    run_until(c, in, 2100);
    CHECK(c.calibrating());
    CHECK(!c.armed());
    in.arm_btn = false;
    run_until(c, in, 2120);
    CHECK(!c.calibrating());
    CHECK_EQ(ch(c, CH_THROTTLE), 1000);
  }

  // Calibration request while armed is ignored.
  {
    TxController c;
    run_until(c, alive(0), 100);
    TxInputs in = alive(110);
    in.arm_btn = true;
    run_until(c, in, 700);
    CHECK(c.armed());
    in.calib_request = true;
    in.now_ms = in.last_phone_ms = 710;
    c.update(in);
    CHECK(!c.calibrating());
    CHECK(c.armed());
  }

  // BEEP while phone alive; dropped when phone goes stale.
  {
    TxController c;
    run_until(c, alive(0), 100);
    TxInputs in = alive(110);
    in.beep = true;
    c.update(in);
    CHECK_EQ(ch(c, CH_BEEPER), 2000);
    in.now_ms = 500;  // last_phone_ms stays 110 -> stale
    c.update(in);
    CHECK_EQ(ch(c, CH_BEEPER), 1000);
  }
}
