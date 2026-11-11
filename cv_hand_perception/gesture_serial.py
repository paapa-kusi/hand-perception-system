import logging


BAUD_RATE = 115200
HEARTBEAT_MS = 200
REPLY_TIMEOUT_MS = 1500
MOVE_TIMEOUT_MS = 9000
LOG = logging.getLogger(__name__)


class GestureController:
    def __init__(self, serial_port, now_ms):
        self.port = serial_port
        self.state = "connecting"
        self.pose = None
        self.pending_pose = None
        self.last_reply_ms = now_ms
        self.deadline_ms = now_ms + 5000
        self.next_ping_ms = now_ms
        self.buffer = bytearray()

    def send(self, command):
        data = (command + "\n").encode("ascii")
        if self.port.write(data) != len(data):
            raise OSError("Incomplete write to gesture controller")

    def arm(self, now_ms):
        if self.state == "disarmed":
            self.send("ARM")
            self.state = "arming"
            self.deadline_ms = now_ms + REPLY_TIMEOUT_MS

    def stop(self, now_ms):
        if self.state not in {"connecting", "stopping"}:
            self.send("STOP")
            self.state = "stopping"
            self.pending_pose = None
            self.deadline_ms = now_ms + REPLY_TIMEOUT_MS

    def move(self, pose, now_ms):
        if self.state == "armed" and pose != self.pose:
            self.send(f"POSE {pose}")
            self.state = "moving"
            self.pending_pose = pose
            self.deadline_ms = now_ms + MOVE_TIMEOUT_MS
            LOG.info("command pose=%s sent_ms=%d", pose, now_ms)

    def poll(self, now_ms):
        self.buffer.extend(self.port.read(min(self.port.in_waiting, 256)))
        while b"\n" in self.buffer:
            line, _, self.buffer = self.buffer.partition(b"\n")
            self.receive(line.decode("ascii", errors="replace").rstrip("\r"), now_ms)
        if len(self.buffer) > 128:
            raise OSError("Overlong reply from gesture controller")

        if self.state in {"connecting", "arming", "moving", "stopping"} and now_ms >= self.deadline_ms:
            raise OSError(f"Timed out while {self.state}")
        if self.state != "connecting" and now_ms - self.last_reply_ms > REPLY_TIMEOUT_MS:
            raise OSError("Gesture controller stopped responding")
        if now_ms >= self.next_ping_ms:
            self.send("HELLO" if self.state == "connecting" else "PING")
            self.next_ping_ms = now_ms + HEARTBEAT_MS

    def receive(self, line, now_ms):
        if line == "READY" and self.state in {"connecting", "disarmed", "arming"}:
            if self.state == "connecting":
                self.state = "disarmed"
        elif line == "ARMED" and self.state == "arming":
            self.state = "armed"
        elif line.startswith("DISARMED ") and self.state != "connecting":
            self.state = "disarmed"
            self.pose = None
            self.pending_pose = None
        elif self.state == "stopping" and line != "BOOT":
            return
        elif line == f"ACK {self.pending_pose}" and self.state == "moving":
            pass
        elif line == f"DONE {self.pending_pose}" and self.state == "moving":
            self.pose = self.pending_pose
            self.pending_pose = None
            self.state = "armed"
        elif line == "BOOT" and self.state == "connecting":
            return
        elif line != "PONG":
            raise OSError(f"Unexpected gesture controller reply: {line!r}")

        self.last_reply_ms = now_ms
        if line != "PONG":
            LOG.info("controller %s received_ms=%d", line, now_ms)

    def close(self):
        try:
            self.send("STOP")
        except OSError:
            # The controller's heartbeat timeout also stops motion.
            pass
        finally:
            self.port.close()
