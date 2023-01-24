import os
import unittest
import tempfile
import pathlib
import time
import random
import threading
import build_stream_collector
# how does this work?
# make a temp file
# sporadically write lines from the originating BEP file
# check that the timings and result match at the end

current_dir = os.path.dirname(os.path.realpath(__file__))
test_path = pathlib.Path(current_dir) / "build_events_target_passed.json"

def write_temp_bep_file_over_time(source_file, out_file):
    with open(source_file, 'r') as source_handle:
        with open(out_file, 'a') as out_file_handle:
            for line in source_handle:
                out_file_handle.write(line)
                random_time = random.randint(10, 200) / 1000.0
                time.sleep(random_time)


class BuildStreamCollectorTest(unittest.TestCase):
    def test_only_build_targets(self):
        _h, temp_file_path = tempfile.mkstemp()

        with open(temp_file_path, 'r') as temp_file_handle:
            file_stream = build_stream_collector.stream_file(temp_file_handle)
            write_thread = threading.Thread(target=write_temp_bep_file_over_time, args=(test_path, temp_file_path))
            write_thread.start()
            time.sleep(0.1)
            collected_targets = build_stream_collector.collect_build_events(file_stream)
            for target_name, target_result in collected_targets.items():
                print("***COLLECTED TARGETS***")
                print(f"[{target_name}]: {target_result}")

        write_thread.join()

        self.assertIn('//app:app_bundle', collected_targets)
        target = collected_targets['//app:app_bundle']
        self.assertEqual(target.name, '//app:app_bundle')
        self.assertEqual(target.type, 'build')
        self.assertEqual(target.state, 'success')
        self.assertGreaterEqual(target.end, target.start)

    def test_mixed_test_failures(self):
        pass

if __name__ == "__main__":
    unittest.main()
