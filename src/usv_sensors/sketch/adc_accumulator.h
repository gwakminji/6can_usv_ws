#pragma once

#include <Arduino.h>

struct AdcAccumulator
{
  uint32_t sum = 0;
  int minValue = 4095;
  int maxValue = 0;
};
