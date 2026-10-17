#include <cstdio>
#include "check.h"

int g_failures = 0;

void run_ibus_tests();

int main() {
  run_ibus_tests();
  if (g_failures) {
    std::printf("%d check(s) failed\n", g_failures);
    return 1;
  }
  std::printf("all tests passed\n");
  return 0;
}
