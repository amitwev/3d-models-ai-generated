// Wire probe: checks the D17 wire to the flight controller pad.
//
// D17 is only read (never driven). With the flight controller powered and
// its UART2 set to MSP, the TX pad idles HIGH, so:
//   D17=1 -> the wire reaches a live UART pin
//   D17=0 -> no connection (the internal pull-down wins)
// The blue LED mirrors the reading.

static const int kProbePin = 17;
static const int kLedPin = 2;

void setup() {
  Serial.begin(115200);
  pinMode(kProbePin, INPUT_PULLDOWN);
  pinMode(kLedPin, OUTPUT);
}

void loop() {
  int v = digitalRead(kProbePin);
  digitalWrite(kLedPin, v);
  Serial.printf("D17=%d %s\n", v, v ? "HIGH: connected" : "LOW: no connection");
  delay(500);
}
