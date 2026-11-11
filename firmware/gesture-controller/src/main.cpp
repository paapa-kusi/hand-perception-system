#include <Arduino.h>
#include <Servo.h>
#include <string.h>

struct Channel {
  uint8_t pin;
  uint8_t openAngle;
  uint8_t peaceAngle;
  bool thumbOrPalm;
};

const Channel channels[] = {
    {2,   0,   0, false},  // Pointer
    {3, 180,   0, true},   // Thumb
    {4,   0, 180, false},  // Pinky
    {5, 180, 180, false},  // Middle
    {6, 100,   0, true},   // Palm
    {7, 180,   0, false},  // Ring
};
const size_t channelCount = sizeof(channels) / sizeof(channels[0]);
const unsigned long stepIntervalMs = 20;
const unsigned long heartbeatTimeoutMs = 1000;

Servo servos[channelCount];
uint8_t angles[channelCount];
bool attached = false;
bool armed = false;
bool moving = false;
bool targetPeace = false;
bool secondPhase = false;
unsigned long lastHeartbeat = 0;
unsigned long lastStep = 0;
char command[24];
size_t commandLength = 0;
bool invalidLine = false;

void reportPose(const __FlashStringHelper *prefix) {
  Serial.print(prefix);
  Serial.println(targetPeace ? F("PEACE") : F("OPEN"));
}

void disarm(const __FlashStringHelper *reason) {
  armed = false;
  moving = false;
  // Hold the last commanded angles. A stop never initiates another pose.
  Serial.print(F("DISARMED "));
  Serial.println(reason);
}

void arm(unsigned long now) {
  if (!attached) {
    // Before the first ARM after reset, the operator parks the hand at OPEN.
    for (size_t i = 0; i < channelCount; ++i) {
      angles[i] = channels[i].openAngle;
      servos[i].write(angles[i]);
      servos[i].attach(channels[i].pin);
    }
    attached = true;
  }
  lastHeartbeat = now;
  armed = true;
  Serial.println(F("ARMED"));
}

void stepMotion(unsigned long now) {
  if (!moving || now - lastStep < stepIntervalMs) return;

  // Close the fingers before folding thumb/palm. Unfold thumb/palm first on opening.
  const bool moveThumbOrPalm = targetPeace == secondPhase;
  bool wroteStep = false;
  for (size_t i = 0; i < channelCount; ++i) {
    const Channel &channel = channels[i];
    if (channel.thumbOrPalm != moveThumbOrPalm) continue;
    const uint8_t target = targetPeace ? channel.peaceAngle : channel.openAngle;
    if (angles[i] == target) continue;

    if (angles[i] < target) ++angles[i];
    else --angles[i];
    servos[i].write(angles[i]);
    wroteStep = true;
  }

  if (wroteStep) {
    lastStep = now;
  } else if (!secondPhase) {
    secondPhase = true;
  } else {
    moving = false;
    reportPose(F("DONE "));
  }
}

void handleCommand(unsigned long now) {
  if (strcmp(command, "STOP") == 0) {
    disarm(F("STOP"));
  } else if (strcmp(command, "HELLO") == 0) {
    armed = false;
    moving = false;
    Serial.println(F("READY"));
  } else if (strcmp(command, "PING") == 0) {
    lastHeartbeat = now;
    Serial.println(F("PONG"));
  } else if (strcmp(command, "ARM") == 0 && !armed) {
    arm(now);
  } else if (strcmp(command, "POSE OPEN") == 0 || strcmp(command, "POSE PEACE") == 0) {
    if (!armed || moving) {
      Serial.println(F("ERR pose requires an idle armed controller"));
      return;
    }
    targetPeace = strcmp(command, "POSE PEACE") == 0;
    secondPhase = false;
    lastStep = now - stepIntervalMs;
    moving = true;
    reportPose(F("ACK "));
  } else {
    Serial.println(F("ERR invalid command"));
  }
}

void readCommands() {
  // Bound serial work per loop so motion and the heartbeat watchdog can run.
  for (uint8_t bytesRead = 0; bytesRead < 32 && Serial.available(); ++bytesRead) {
    const char byte = Serial.read();
    if (byte == '\n') {
      if (invalidLine) Serial.println(F("ERR invalid line"));
      else if (commandLength != 0) {
        command[commandLength] = '\0';
        handleCommand(millis());
      }
      commandLength = 0;
      invalidLine = false;
    } else if (byte != '\r') {
      if (byte < ' ' || byte > '~' || commandLength == sizeof(command) - 1) {
        invalidLine = true;
      } else if (!invalidLine) {
        command[commandLength++] = byte;
      }
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println(F("BOOT"));
}

void loop() {
  if (armed && millis() - lastHeartbeat >= heartbeatTimeoutMs) disarm(F("TIMEOUT"));
  readCommands();
  stepMotion(millis());
}
