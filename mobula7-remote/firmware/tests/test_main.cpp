#include <cstdio>
#include "check.h"

int g_failures = 0;

void run_ibus_tests();
void run_packet_tests();

int main() {
  run_ibus_tests();
  run_packet_tests();
  if (g_failures) {
    std::printf("%d check(s) failed\n", g_failures);
    return 1;
  }
  std::printf("all tests passed\n");
  return 0;
}
