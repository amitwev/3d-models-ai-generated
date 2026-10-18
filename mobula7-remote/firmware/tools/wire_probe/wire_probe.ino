// Wire probe: checks the D17 wire to the flight controller pad.
//
// D17 is only read (never driven). It is read twice, once with the internal
// pull-down and once with the pull-up. With the flight controller powered
// and its UART2 set to MSP, the TX pad idles HIGH, so:
//   down=1 up=1 -> the wire reaches a live UART pin
//   down=0 up=1 -> nothing drives the wire (open: bad joint or wrong pad)
//   down=0 up=0 -> the wire is shorted to GND (solder bridge)
// The blue LED is on only for the "connected" case.

static const int kProbePin = 17;
static const int kLedPin = 2;

static int read_with(int mode) {
  pinMode(kProbePin, mode);
  delay(5);
  return digitalRead(kProbePin);
}

void setup() {
  Serial.begin(115200);
  pinMode(kLedPin, OUTPUT);
}

void loop() {
  int down = read_with(INPUT_PULLDOWN);
  int up = read_with(INPUT_PULLUP);
  const char* verdict;
  if (down && up) verdict = "CONNECTED to the FC";
  else if (!down && up) verdict = "OPEN: no connection";
  else if (!down && !up) verdict = "SHORT to GND";
  else verdict = "unexpected";
  digitalWrite(kLedPin, (down && up) ? HIGH : LOW);
  Serial.printf("down=%d up=%d -> %s\n", down, up, verdict);
  delay(500);
}
