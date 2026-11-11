import unittest

from cv_hand_perception.gesture_serial import GestureController
from cv_hand_perception.gestures import GestureGate, Observation


class GestureGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = GestureGate()

    def observe(self, timestamp, label="Victory", score=0.9, *, age=0):
        return self.gate.observe(Observation(timestamp, label, score), timestamp + age)

    def test_accepts_once_per_stable_pose_change(self):
        self.assertIsNone(self.observe(0))
        self.assertIsNone(self.observe(100))
        self.assertEqual(self.observe(200), "PEACE")
        self.assertIsNone(self.observe(300))
        self.assertIsNone(self.observe(400, "Open_Palm"))
        self.assertIsNone(self.observe(500, "Open_Palm"))
        self.assertEqual(self.observe(600, "Open_Palm"), "OPEN")

    def test_unsupported_low_confidence_and_missing_hand_clear_the_dwell(self):
        for label, score in [("Closed_Fist", 0.99), ("Victory", 0.6), ("No single hand", 0)]:
            with self.subTest(label=label, score=score):
                self.gate = GestureGate()
                self.assertIsNone(self.observe(0))
                self.assertIsNone(self.observe(100, label, score))
                self.assertIsNone(self.observe(200))
                self.assertIsNone(self.observe(300))
                self.assertEqual(self.observe(400), "PEACE")

    def test_gaps_stale_results_and_duplicate_timestamps_cannot_complete_a_dwell(self):
        self.assertIsNone(self.observe(0))
        self.assertIsNone(self.observe(200))
        self.assertIsNone(self.observe(200))
        self.assertIsNone(self.observe(300))
        self.assertIsNone(self.observe(400, age=151))
        self.assertIsNone(self.observe(600))
        self.assertIsNone(self.observe(700))
        self.assertEqual(self.observe(800), "PEACE")


class FakeSerial:
    def __init__(self):
        self.incoming = bytearray()
        self.writes = []

    @property
    def in_waiting(self):
        return len(self.incoming)

    def read(self, count):
        result = self.incoming[:count]
        del self.incoming[:count]
        return result

    def write(self, data):
        self.writes.append(data)
        return len(data)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.port = FakeSerial()
        self.controller = GestureController(self.port, now_ms=0)
        self.controller.poll(0)
        self.reply(b"BOOT\r\nREADY\r\n", 100)

    def reply(self, data, now_ms):
        self.port.incoming.extend(data)
        self.controller.poll(now_ms)

    def arm(self):
        self.controller.arm(110)
        self.reply(b"ARMED\r\n", 120)

    def test_arm_and_finish_before_next_pose_is_sent(self):
        self.controller.move("PEACE", 105)
        self.assertEqual(self.port.writes, [b"HELLO\n"])
        self.arm()
        self.controller.move("PEACE", 125)
        self.controller.move("OPEN", 126)
        self.reply(b"ACK PEACE\r\nDONE PE", 130)
        self.assertEqual(self.controller.state, "moving")
        self.reply(b"ACE\r\n", 140)
        self.controller.move("PEACE", 145)
        self.controller.move("OPEN", 150)
        self.assertEqual(self.port.writes, [b"HELLO\n", b"ARM\n", b"POSE PEACE\n", b"POSE OPEN\n"])

    def test_stop_and_timeout_discard_pending_motion_and_require_rearming(self):
        self.arm()
        self.controller.move("PEACE", 125)
        self.controller.stop(130)
        self.reply(b"ACK PEACE\r\nDISARMED STOP\r\n", 135)
        self.controller.move("OPEN", 140)
        self.assertEqual(self.port.writes[-1], b"STOP\n")
        self.assertEqual(self.controller.state, "disarmed")
        self.controller.arm(145)
        self.reply(b"ARMED\r\n", 150)
        self.controller.move("OPEN", 155)
        self.reply(b"DISARMED TIMEOUT\r\n", 160)
        self.assertIsNone(self.controller.pending_pose)
        self.assertEqual(self.controller.state, "disarmed")

    def test_board_reset_fails_the_connection(self):
        self.arm()
        with self.assertRaisesRegex(OSError, "BOOT"):
            self.reply(b"BOOT\r\n", 125)
