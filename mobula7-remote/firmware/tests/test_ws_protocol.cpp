#include <cstring>

#include "check.h"
#include "Mobula7Link.h"

using namespace m7;

static bool parse(const char* s, StickMsg* m) { return parse_stick_msg(s, std::strlen(s), m); }

void run_ws_protocol_tests() {
  StickMsg m{};
  CHECK(parse("S,1500,1600,1000,1400,0,1", &m));
  CHECK_EQ(m.roll, 1500);
  CHECK_EQ(m.pitch, 1600);
  CHECK_EQ(m.throttle, 1000);
  CHECK_EQ(m.yaw, 1400);
  CHECK(!m.beep);
  CHECK(m.calib);

  // Out-of-range values are clamped, never passed through.
  CHECK(parse("S,5000,1500,1000,1500,0,0", &m));
  CHECK_EQ(m.roll, 2000);
  CHECK(parse("S,0,1500,1000,1500,1,0", &m));
  CHECK_EQ(m.roll, 1000);
  CHECK(m.beep);

  // Malformed messages are rejected.
  CHECK(!parse("S,1500,1500,1000,1500,0", &m));        // 6 fields
  CHECK(!parse("S,1500,1500,1000,1500,0,0,9", &m));    // 8 fields
  CHECK(!parse("X,1500,1500,1000,1500,0,0", &m));      // wrong tag
  CHECK(!parse("S,15a0,1500,1000,1500,0,0", &m));      // non-numeric
  CHECK(!parse("S,1500,1500,1000,1500,2,0", &m));      // beep not 0/1
  CHECK(!parse("S,99999,1500,1000,1500,0,0", &m));     // > 4 digits
  CHECK(!parse("S,,1500,1000,1500,0,0", &m));          // empty field
  CHECK(!parse("S,-5,1500,1000,1500,0,0", &m));        // sign
  CHECK(!parse("", &m));
  const char* full = "S,1500,1500,1000,1500,0,0";
  CHECK(!parse_stick_msg(full, 9, &m));                // cut mid-number

  char buf[16];
  CHECK_EQ(format_status(buf, sizeof(buf), true, false, false), 7);
  CHECK(std::strcmp(buf, "T,1,0,0") == 0);
  CHECK_EQ(format_status(buf, sizeof(buf), false, true, true), 7);
  CHECK(std::strcmp(buf, "T,0,1,1") == 0);
  CHECK_EQ(format_status(buf, 7, true, false, false), -1);  // no room for NUL
}
