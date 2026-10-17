#include "check.h"
#include "Mobula7Link.h"

void run_ibus_tests() {
  uint16_t ch[m7::kNumChannels];
  for (auto& c : ch) c = 1500;
  ch[m7::CH_THROTTLE] = 1000;
  uint8_t f[m7::kIbusFrameLen];
  m7::ibus_build_frame(ch, f);

  CHECK_EQ(f[0], 0x20);
  CHECK_EQ(f[1], 0x40);
  CHECK_EQ(f[2] | (f[3] << 8), 1500);  // CH1 little-endian
  CHECK_EQ(f[6] | (f[7] << 8), 1000);  // CH3
  uint16_t sum = 0xFFFF;
  for (int i = 0; i < 30; i++) sum -= f[i];
  CHECK_EQ(f[30] | (f[31] << 8), sum);  // 0xFFFF - sum(bytes 0..29)

  ch[0] = 2500;
  ch[1] = 10;
  m7::ibus_build_frame(ch, f);
  CHECK_EQ(f[2] | (f[3] << 8), 2000);  // clamped high
  CHECK_EQ(f[4] | (f[5] << 8), 1000);  // clamped low
}
