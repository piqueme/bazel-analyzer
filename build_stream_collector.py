import argparse
from io import TextIOWrapper
from typing import Literal, Generator, Iterable
import pathlib
import dataclasses
import datetime
import json
import time

TargetName = str

@dataclasses.dataclass
class TargetResult:
    name: TargetName
    type: Literal["build", "test"] | None
    start: int | None
    end: int | None
    state: Literal["success", "fail", "incomplete"] | None

CollectedTargets = dict[TargetName, TargetResult]

def stream_file(file_handle: TextIOWrapper) -> Generator[str, None, None]:
    file_handle.seek(0, 2)
    while True:
        line = file_handle.readline()
        if not line:
            time.sleep(0.1)
            continue
        yield line


def collect_build_events(file_stream: Iterable[str]) -> CollectedTargets:
    collected_targets: CollectedTargets = {}
    for line in file_stream:
        parsed_line = json.loads(line)

        if parsed_line.get("id", {}).get("targetConfigured"):
            target_name = parsed_line.get("id", {}).get("targetConfigured", {}).get("label")
            start_time = int(datetime.datetime.now().timestamp() * 1000)
            target_result = TargetResult(
                name = target_name,
                type = "build",
                start = start_time,
                end = None,
                state = None,
            )
            collected_targets[target_name] = target_result

        if parsed_line.get("id", {}).get("targetCompleted"):
            target_name = parsed_line.get("id", {}).get("targetCompleted", {}).get("label")
            if target_name not in collected_targets:
                print(f"[WARN] Target completion event for untracked target {target_name}. Ignoring.")

            end_time = int(datetime.datetime.now().timestamp() * 1000)
            completed = parsed_line.get("completed", {})
            success = False
            if "success" in completed:
                success = True
            if "failureDetail" in completed:
                success = False
            state = "success" if success else "fail"
            collected_targets[target_name].end = end_time
            collected_targets[target_name].state = state

        if parsed_line.get("id", {}).get("testResult"):
            target_name = parsed_line.get("id", {}).get("testResult", {}).get("label")
            test_result = parsed_line.get("testResult", {})
            start_time = None
            end_time = None

            if "testAttemptStart" in test_result:
                start_time = datetime.datetime.fromisoformat(test_result["testAttemptStart"])

                if "testAttemptDuration" in test_result:
                    duration = datetime.timedelta(seconds = float(test_result["testAttemptDuration"]))
                    end_time = start_time + duration

            state = 'incomplete'
            test_status = test_result.get("status", "INCOMPLETE")
            if test_status == 'PASSED':
                state = 'success'
            if test_status == 'FAILED':
                state = 'fail'

            parsed_result = TargetResult(
                name = target_name,
                type = "test",
                start = start_time.microsecond // 1000 if start_time else None,
                end = end_time.microsecond // 1000 if end_time else None,
                state = state
            )

            collected_targets[target_name] = parsed_result

        if parsed_line.get("id", {}).get("buildFinished") is not None:
            break

    for target_name, target_result in collected_targets.items():
        if not target_result.state:
            target_result.state = 'incomplete'

    return collected_targets


class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            return super().default(o)

def main(args: argparse.Namespace):
    with open(args.bep_file, 'r') as file_handle:
        event_stream = stream_file(file_handle)
        collected_targets = collect_build_events(event_stream)
        collected_targets_json = json.dumps(collected_targets, cls=EnhancedJSONEncoder)

    with open(args.output_file, 'w') as output_handle: 
        if collected_targets_json:
            output_handle.write(collected_targets_json)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bep_file", required=True, type=pathlib.Path)
    parser.add_argument("--output_file", required=True, type=pathlib.Path)
    
    args = parser.parse_args()
    main(args)
