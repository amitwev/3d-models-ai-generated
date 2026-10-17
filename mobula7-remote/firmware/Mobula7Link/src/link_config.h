// Constants shared by the remote (TX) and the drone-side receiver (RX).
#pragma once
#include <stddef.h>
#include <stdint.h>

namespace m7 {

constexpr int kNumChannels = 14;

constexpr uint16_t kChLow = 1000;
constexpr uint16_t kChMid = 1500;
constexpr uint16_t kChHigh = 2000;

// Channel indexes, AETR order (Betaflight `map AETR1234`).
enum ChannelIndex : int {
  CH_ROLL = 0,
  CH_PITCH = 1,
  CH_THROTTLE = 2,
  CH_YAW = 3,
  CH_ARM = 4,     // AUX1
  CH_ANGLE = 5,   // AUX2, always low (Angle mode on)
  CH_BEEPER = 6,  // AUX3
};

constexpr uint8_t kWifiChannel = 6;

constexpr uint32_t kRxLinkTimeoutMs = 150;
constexpr uint32_t kPhoneTimeoutMs = 300;
constexpr uint32_t kArmHoldMs = 500;
constexpr uint32_t kCalibDurationMs = 2000;
constexpr uint16_t kArmThrottleMax = 1050;

inline uint16_t clamp_ch(int v) {
  if (v < kChLow) return kChLow;
  if (v > kChHigh) return kChHigh;
  return (uint16_t)v;
}

// Disarmed, throttle low, sticks centred, Angle on, beeper off.
inline void safe_channels(uint16_t out[kNumChannels]) {
  for (int i = 0; i < kNumChannels; i++) out[i] = kChMid;
  out[CH_THROTTLE] = kChLow;
  out[CH_ARM] = kChLow;
  out[CH_ANGLE] = kChLow;
  out[CH_BEEPER] = kChLow;
}

}  // namespace m7
