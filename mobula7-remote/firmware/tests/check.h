// Minimal test assertions for host-side unit tests.
#pragma once
#include <cstdio>

extern int g_failures;

#define CHECK(cond)                                                     \
  do {                                                                  \
    if (!(cond)) {                                                      \
      std::printf("%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond); \
      g_failures++;                                                     \
    }                                                                   \
  } while (0)

#define CHECK_EQ(a, b)                                                  \
  do {                                                                  \
    long long _a = (long long)(a), _b = (long long)(b);                 \
    if (_a != _b) {                                                     \
      std::printf("%s:%d: CHECK_EQ failed: %s == %s (%lld vs %lld)\n",  \
                  __FILE__, __LINE__, #a, #b, _a, _b);                  \
      g_failures++;                                                     \
    }                                                                   \
  } while (0)
