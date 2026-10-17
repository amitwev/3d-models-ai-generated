// Text messages between the phone page and the remote (WebSocket).
//   phone -> remote: "S,<roll>,<pitch>,<throttle>,<yaw>,<beep 0|1>,<calib 0|1>"
//   remote -> phone: "T,<armed>,<killed>,<calibrating>"
#pragma once
#include "link_config.h"

namespace m7 {

struct StickMsg {
  uint16_t roll, pitch, throttle, yaw;
  bool beep, calib;
};

inline bool parse_stick_msg(const char* s, size_t len, StickMsg* out) {
  if (s == nullptr || len < 2 || s[0] != 'S' || s[1] != ',') return false;
  int vals[6];
  size_t i = 2;
  for (int f = 0; f < 6; f++) {
    int v = 0, digits = 0;
    while (i < len && s[i] >= '0' && s[i] <= '9') {
      if (++digits > 4) return false;
      v = v * 10 + (s[i] - '0');
      i++;
    }
    if (digits == 0) return false;
    vals[f] = v;
    if (f < 5) {
      if (i >= len || s[i] != ',') return false;
      i++;
    }
  }
  if (i != len) return false;
  if (vals[4] > 1 || vals[5] > 1) return false;
  out->roll = clamp_ch(vals[0]);
  out->pitch = clamp_ch(vals[1]);
  out->throttle = clamp_ch(vals[2]);
  out->yaw = clamp_ch(vals[3]);
  out->beep = vals[4] == 1;
  out->calib = vals[5] == 1;
  return true;
}

inline int format_status(char* buf, size_t n, bool armed, bool killed,
                         bool calibrating) {
  const size_t kLen = 7;  // "T,a,k,c"
  if (buf == nullptr || n < kLen + 1) return -1;
  buf[0] = 'T';
  buf[1] = ',';
  buf[2] = armed ? '1' : '0';
  buf[3] = ',';
  buf[4] = killed ? '1' : '0';
  buf[5] = ',';
  buf[6] = calibrating ? '1' : '0';
  buf[7] = '\0';
  return (int)kLen;
}

}  // namespace m7
