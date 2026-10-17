// FlySky iBUS servo frame: 0x20 0x40, 14 little-endian channels, checksum.
#pragma once
#include "link_config.h"

namespace m7 {

constexpr int kIbusFrameLen = 32;

inline void ibus_build_frame(const uint16_t ch[kNumChannels],
                             uint8_t out[kIbusFrameLen]) {
  out[0] = 0x20;
  out[1] = 0x40;
  for (int i = 0; i < kNumChannels; i++) {
    uint16_t v = clamp_ch(ch[i]);
    out[2 + i * 2] = (uint8_t)(v & 0xFF);
    out[3 + i * 2] = (uint8_t)(v >> 8);
  }
  uint16_t sum = 0xFFFF;
  for (int i = 0; i < kIbusFrameLen - 2; i++) sum -= out[i];
  out[30] = (uint8_t)(sum & 0xFF);
  out[31] = (uint8_t)(sum >> 8);
}

}  // namespace m7
