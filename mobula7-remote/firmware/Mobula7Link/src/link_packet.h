// ESP-NOW control packet sent from the remote (TX) to the drone (RX).
#pragma once
#include <string.h>

#include "link_config.h"

namespace m7 {

constexpr uint32_t kPacketMagic = 0x4D375258;  // 'M7RX'
constexpr uint8_t kPacketVersion = 1;

struct __attribute__((packed)) LinkPacket {
  uint32_t magic;
  uint8_t version;
  uint8_t flags;  // reserved, 0
  uint16_t seq;
  uint16_t ch[kNumChannels];
  uint16_t crc;  // CRC-16/CCITT-FALSE over all preceding bytes
};
static_assert(sizeof(LinkPacket) == 38, "LinkPacket layout changed");

inline uint16_t crc16_ccitt(const uint8_t* d, size_t n) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < n; i++) {
    crc ^= (uint16_t)d[i] << 8;
    for (int b = 0; b < 8; b++)
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
  }
  return crc;
}

inline void packet_seal(LinkPacket& p) {
  p.magic = kPacketMagic;
  p.version = kPacketVersion;
  p.crc = crc16_ccitt((const uint8_t*)&p, sizeof(LinkPacket) - sizeof(p.crc));
}

inline bool packet_parse(const uint8_t* data, int len, LinkPacket* out) {
  if (data == nullptr || len != (int)sizeof(LinkPacket)) return false;
  LinkPacket p;
  memcpy(&p, data, sizeof(p));
  if (p.magic != kPacketMagic || p.version != kPacketVersion) return false;
  if (p.crc != crc16_ccitt(data, sizeof(LinkPacket) - sizeof(p.crc))) return false;
  *out = p;
  return true;
}

}  // namespace m7
