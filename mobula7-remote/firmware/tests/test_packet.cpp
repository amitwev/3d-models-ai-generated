#include <cstring>

#include "check.h"
#include "Mobula7Link.h"

using m7::LinkPacket;

static LinkPacket sample() {
  LinkPacket p;
  std::memset(&p, 0, sizeof(p));
  p.seq = 4242;
  for (int i = 0; i < m7::kNumChannels; i++) p.ch[i] = (uint16_t)(1000 + i * 50);
  m7::packet_seal(p);
  return p;
}

void run_packet_tests() {
  CHECK_EQ(m7::crc16_ccitt((const uint8_t*)"123456789", 9), 0x29B1);

  LinkPacket p = sample();
  CHECK_EQ(p.magic, m7::kPacketMagic);
  CHECK_EQ(p.version, m7::kPacketVersion);
  LinkPacket out;
  const uint8_t* raw = (const uint8_t*)&p;
  CHECK(m7::packet_parse(raw, sizeof(p), &out));
  CHECK_EQ(out.seq, 4242);
  for (int i = 0; i < m7::kNumChannels; i++) CHECK_EQ(out.ch[i], p.ch[i]);

  // Foreign or damaged traffic is rejected.
  CHECK(!m7::packet_parse(raw, sizeof(p) - 1, &out));
  uint8_t longer[sizeof(LinkPacket) + 1];
  std::memcpy(longer, raw, sizeof(p));
  longer[sizeof(p)] = 0;
  CHECK(!m7::packet_parse(longer, sizeof(longer), &out));
  CHECK(!m7::packet_parse(raw, 0, &out));

  LinkPacket bad = p;
  bad.magic ^= 1;
  CHECK(!m7::packet_parse((const uint8_t*)&bad, sizeof(bad), &out));

  bad = p;
  bad.version = 2;
  CHECK(!m7::packet_parse((const uint8_t*)&bad, sizeof(bad), &out));

  bad = p;
  ((uint8_t*)&bad.ch[3])[0] ^= 0x01;  // corrupt after sealing
  CHECK(!m7::packet_parse((const uint8_t*)&bad, sizeof(bad), &out));
}
