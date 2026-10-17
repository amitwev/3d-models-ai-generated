// Drone-side link state: turns received packets into channels that are
// always safe to send to the flight controller.
#pragma once
#include "link_packet.h"

namespace m7 {

class RxLink {
 public:
  void on_packet(const LinkPacket& p, uint32_t now_ms) {
    if (!link_ok(now_ms)) need_disarm_ = true;  // link was lost before this packet
    for (int i = 0; i < kNumChannels; i++) ch_[i] = clamp_ch(p.ch[i]);
    last_ms_ = now_ms;
    has_packet_ = true;
    if (ch_[CH_ARM] < kChMid) need_disarm_ = false;
  }

  bool link_ok(uint32_t now_ms) const {
    return has_packet_ && (uint32_t)(now_ms - last_ms_) <= kRxLinkTimeoutMs;
  }

  // After a lost link, ARM stays low until the remote sends a disarmed packet.
  void output(uint32_t now_ms, uint16_t out[kNumChannels]) const {
    if (!link_ok(now_ms)) {
      safe_channels(out);
      return;
    }
    for (int i = 0; i < kNumChannels; i++) out[i] = ch_[i];
    if (need_disarm_) out[CH_ARM] = kChLow;
  }

 private:
  uint16_t ch_[kNumChannels] = {};
  uint32_t last_ms_ = 0;
  bool has_packet_ = false;
  bool need_disarm_ = true;
};

}  // namespace m7
