#include <cstdio>
#include "check.h"

int g_failures = 0;

void run_ibus_tests();
void run_packet_tests();
void run_rx_link_tests();
void run_tx_controller_tests();

int main() {
  run_ibus_tests();
  run_packet_tests();
  run_rx_link_tests();
  run_tx_controller_tests();
  if (g_failures) {
    std::printf("%d check(s) failed\n", g_failures);
    return 1;
  }
  std::printf("all tests passed\n");
  return 0;
}
