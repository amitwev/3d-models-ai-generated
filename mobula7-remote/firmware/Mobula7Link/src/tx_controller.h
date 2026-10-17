// Remote-side logic: physical ARM/KILL buttons + phone sticks -> channels.
// Arming only ever comes from the physical ARM button.
#pragma once
#include "link_config.h"

namespace m7 {

struct TxInputs {
  uint32_t now_ms;
  bool arm_btn;               // pressed, already debounced
  bool kill_btn;              // pressed, already debounced
  bool phone_connected;       // a WebSocket client exists
  uint32_t last_phone_ms;     // time of last valid stick message
  uint16_t roll, pitch, throttle, yaw;
  bool beep;                  // BEEP held on the page
  bool calib_request;         // one-shot: "calibrate" pressed this cycle
};

class TxController {
 public:
  void update(const TxInputs& in) {
    now_ = in.now_ms;
    in_ = in;
    phone_alive_ = in.phone_connected &&
                   (uint32_t)(in.now_ms - in.last_phone_ms) <= kPhoneTimeoutMs;

    if (calibrating_ && (uint32_t)(now_ - calib_start_) >= kCalibDurationMs)
      calibrating_ = false;

    if (in.kill_btn || !phone_alive_) {
      armed_ = false;
      calibrating_ = false;
      killed_ = true;
    } else if (killed_ && !in.arm_btn) {
      killed_ = false;  // KILL released, phone alive, ARM released
    }

    // Track ARM presses. A press only counts if it started while nothing
    // (kill latch, calibration) was blocking.
    if (!in.arm_btn) {
      arm_down_ = false;
    } else if (!arm_down_) {
      arm_down_ = true;
      arm_start_ = now_;
      arm_valid_ = !killed_ && !calibrating_;
    }
    if (killed_ || calibrating_) arm_valid_ = false;

    if (!armed_ && arm_down_ && arm_valid_ && in.throttle < kArmThrottleMax &&
        (uint32_t)(now_ - arm_start_) >= kArmHoldMs) {
      armed_ = true;
    }

    if (in.calib_request && !armed_ && !killed_ && !calibrating_) {
      calibrating_ = true;
      calib_start_ = now_;
      arm_valid_ = false;
    }
  }

  void channels(uint16_t out[kNumChannels]) const {
    safe_channels(out);
    if (killed_ || !phone_alive_) return;
    if (calibrating_) {
      // Betaflight stick command (Mode 2): throttle high, yaw left, pitch down.
      out[CH_THROTTLE] = kChHigh;
      out[CH_YAW] = kChLow;
      out[CH_PITCH] = kChLow;
      return;
    }
    out[CH_ROLL] = clamp_ch(in_.roll);
    out[CH_PITCH] = clamp_ch(in_.pitch);
    out[CH_THROTTLE] = clamp_ch(in_.throttle);
    out[CH_YAW] = clamp_ch(in_.yaw);
    out[CH_ARM] = armed_ ? kChHigh : kChLow;
    out[CH_BEEPER] = in_.beep ? kChHigh : kChLow;
  }

  bool armed() const { return armed_; }
  bool killed() const { return killed_; }
  bool calibrating() const { return calibrating_; }
  bool phone_alive() const { return phone_alive_; }

 private:
  TxInputs in_{};
  uint32_t now_ = 0;
  bool phone_alive_ = false;
  bool armed_ = false;
  bool killed_ = true;  // start latched: power-up with ARM held must not arm
  bool calibrating_ = false;
  uint32_t calib_start_ = 0;
  bool arm_down_ = false;
  bool arm_valid_ = false;
  uint32_t arm_start_ = 0;
};

}  // namespace m7
