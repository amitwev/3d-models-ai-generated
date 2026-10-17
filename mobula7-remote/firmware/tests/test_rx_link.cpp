#include <cstring>

#include "check.h"
#include "Mobula7Link.h"

using namespace m7;

static LinkPacket pkt(uint16_t arm, uint16_t throttle) {
  LinkPacket p;
  std::memset(&p, 0, sizeof(p));
  for (int i = 0; i < kNumChannels; i++) p.ch[i] = kChMid;
  p.ch[CH_ARM] = arm;
  p.ch[CH_THROTTLE] = throttle;
  p.ch[CH_ANGLE] = kChLow;
  packet_seal(p);
  return p;
}

static bool is_safe(const uint16_t* out) {
  uint16_t s[kNumChannels];
  safe_channels(s);
  return std::memcmp(out, s, sizeof(s)) == 0;
}

void run_rx_link_tests() {
  uint16_t out[kNumChannels];

  // Never received anything: safe output.
  {
    RxLink rx;
    rx.output(0, out);
    CHECK(is_safe(out));
    CHECK(!rx.link_ok(0));
  }

  // Starts latched: ARM forced low until a disarmed packet is seen.
  {
    RxLink rx;
    rx.on_packet(pkt(2000, 1400), 0);
    rx.output(0, out);
    CHECK_EQ(out[CH_ARM], 1000);
    CHECK_EQ(out[CH_THROTTLE], 1400);

    rx.on_packet(pkt(1000, 1000), 10);
    rx.on_packet(pkt(2000, 1300), 20);
    rx.output(20, out);
    CHECK_EQ(out[CH_ARM], 2000);

    // 150 ms is still ok, 151 ms is loss.
    rx.output(170, out);
    CHECK_EQ(out[CH_ARM], 2000);
    CHECK(rx.link_ok(170));
    rx.output(171, out);
    CHECK(is_safe(out));
    CHECK(!rx.link_ok(171));

    // Link returns with ARM still high: must stay disarmed (re-latched).
    rx.on_packet(pkt(2000, 1300), 300);
    rx.output(300, out);
    CHECK_EQ(out[CH_ARM], 1000);
  }

  // Outage with no output() call in between still re-latches.
  {
    RxLink rx;
    rx.on_packet(pkt(1000, 1000), 0);
    rx.on_packet(pkt(2000, 1200), 10);
    rx.on_packet(pkt(2000, 1200), 500);  // 490 ms gap, never polled
    rx.output(500, out);
    CHECK_EQ(out[CH_ARM], 1000);
  }

  // millis() wraparound.
  {
    RxLink rx;
    rx.on_packet(pkt(1000, 1000), 0xFFFFFFF0u);
    CHECK(rx.link_ok(0x00000010u));   // 32 ms later
    CHECK(!rx.link_ok(0x000000A0u));  // 176 ms later
  }

  // Out-of-range channel values are clamped.
  {
    RxLink rx;
    LinkPacket p = pkt(1000, 1000);
    p.ch[CH_ROLL] = 2600;
    packet_seal(p);
    rx.on_packet(p, 5);
    rx.output(5, out);
    CHECK_EQ(out[CH_ROLL], 2000);
  }
}
