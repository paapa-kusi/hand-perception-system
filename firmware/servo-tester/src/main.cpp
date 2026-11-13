#include <Arduino.h>
#include <Servo.h>

// Multi-finger servo finder (ELEGOO Mega 2560, MG996R servos, external power)
// Servo signal pins: 2, 3, 4, 5, 6 and 7. Add more pins to PINS[] as you wire them.
//
// Serial Monitor (9600 baud). Type a command, press Enter:
//   2:90      move pin 2 to 90 degrees (slowly)
//   4:+       nudge pin 4 up 5 degrees   (4:-  nudges down)
//   all:90    move every finger to 90 together
//   90        move the last-used finger to 90
//   + / -     nudge the last-used finger
//   d         detach ALL servos (limp, emergency stop)    d4 = detach only pin 4
//   ?         show each finger's current angle

const int NUM = 6;
const int PINS[NUM] = {2, 3, 4, 5, 6, 7};
const int STEP_DELAY_MS = 20;   // bigger = slower

Servo servos[NUM];
int cur[NUM] = {-1, -1, -1, -1, -1, -1};     // -1 = unknown until first command
int sel = 0;                    // last-used finger index

int findIndex(int pin) {
  for (int i = 0; i < NUM; i++) if (PINS[i] == pin) return i;
  return -1;
}

void moveSet(const bool active[], const int targetIn[]) {
  int target[NUM];
  for (int i = 0; i < NUM; i++) {
    if (!active[i]) continue;
    target[i] = constrain(targetIn[i], 0, 180);
    if (cur[i] < 0) {                       // first move: unknown start, jump there
      servos[i].write(target[i]);
      servos[i].attach(PINS[i]);
      cur[i] = target[i];
    } else if (!servos[i].attached()) {
      servos[i].write(cur[i]);
      servos[i].attach(PINS[i]);
    }
  }
  bool moving = true;
  while (moving) {
    moving = false;
    for (int i = 0; i < NUM; i++) {
      if (!active[i] || cur[i] == target[i]) continue;
      cur[i] += (target[i] > cur[i]) ? 1 : -1;
      servos[i].write(cur[i]);
      moving = true;
    }
    if (moving) delay(STEP_DELAY_MS);
    if (Serial.available() && Serial.peek() == 'd') break;   // stop mid-move
  }
  for (int i = 0; i < NUM; i++) {
    if (!active[i]) continue;
    Serial.print("Pin ");
    Serial.print(PINS[i]);
    Serial.print(" angle: ");
    Serial.println(cur[i]);
  }
}

void setup() {
  Serial.begin(9600);
  Serial.println("Multi-finger servo finder ready. Servos are limp until you send an angle.");
  Serial.println("Examples: 2:90   4:+   all:90   d (limp)   ? (angles)");
}

void loop() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd.length() == 0) return;

  if (cmd == "?") {
    for (int i = 0; i < NUM; i++) {
      Serial.print("Pin ");
      Serial.print(PINS[i]);
      Serial.print(": ");
      if (cur[i] < 0) Serial.println("unknown (not moved yet)");
      else Serial.println(cur[i]);
    }
    return;
  }

  if (cmd[0] == 'd') {
    if (cmd.length() == 1) {
      for (int i = 0; i < NUM; i++) servos[i].detach();
      Serial.println("All detached (limp). Send an angle to re-engage.");
    } else {
      int i = findIndex(cmd.substring(1).toInt());
      if (i < 0) { Serial.println("Unknown pin."); return; }
      servos[i].detach();
      Serial.print("Pin ");
      Serial.print(PINS[i]);
      Serial.println(" detached (limp).");
    }
    return;
  }

  String who = "";
  String val = cmd;
  int colon = cmd.indexOf(':');
  if (colon >= 0) {
    who = cmd.substring(0, colon);
    who.trim();
    val = cmd.substring(colon + 1);
    val.trim();
  }

  bool active[NUM] = {false};
  if (who == "all") {
    for (int i = 0; i < NUM; i++) active[i] = true;
  } else if (who.length() > 0) {
    int i = findIndex(who.toInt());
    if (i < 0) { Serial.println("Unknown pin. Wired pins are in PINS[]."); return; }
    sel = i;
    active[i] = true;
  } else {
    active[sel] = true;
  }

  int target[NUM];
  for (int i = 0; i < NUM; i++) {
    int base = (cur[i] < 0) ? 90 : cur[i];
    if (val == "+") target[i] = base + 5;
    else if (val == "-") target[i] = base - 5;
    else target[i] = val.toInt();
  }
  moveSet(active, target);
}
