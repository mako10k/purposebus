import os
import unittest

from purposebus.util import (
    current_boot_id,
    filters_overlap,
    process_matches,
    process_start_identity,
    topic_matches,
)


class TopicTest(unittest.TestCase):
    def test_topic_matching(self):
        self.assertTrue(topic_matches("test/+", "test/result"))
        self.assertTrue(topic_matches("test/#", "test/result/detail"))
        self.assertFalse(topic_matches("test/+", "test/result/detail"))

    def test_filter_overlap(self):
        self.assertTrue(filters_overlap("test/+", "test/#"))
        self.assertTrue(filters_overlap("a/+/c", "a/b/+"))
        self.assertFalse(filters_overlap("a/b", "a/c"))


class ProcessIdentityTest(unittest.TestCase):
    def test_wrong_start_identity_detects_pid_reuse(self):
        pid = os.getpid()
        start = process_start_identity(pid)
        boot = current_boot_id()
        if start is None or boot is None:
            self.skipTest("Linux process identity is unavailable")
        matches, reason = process_matches(os.uname().nodename, boot, pid, start + "-different")
        self.assertFalse(matches)
        self.assertEqual(reason, "pid_reused")


if __name__ == "__main__":
    unittest.main()
