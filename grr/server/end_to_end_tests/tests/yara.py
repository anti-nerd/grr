#!/usr/bin/env python
"""End to end tests for Yara based flows."""

from grr import config
from grr.server.end_to_end_tests import test_base


def GetProcessName(platform):
  """Gets the process name for the different platforms.

  By default, this function will return:
    Windows: GRRservice.exe
    Linux: grrd
    Darwin: grr

  Args:
    platform: The platform the client under test is running on.

  Returns:
     The process name the test should use.

  Raises:
    ValueError: An unknown platform was passed.
  """
  if platform == test_base.EndToEndTest.Platform.WINDOWS:
    return config.CONFIG.Get(
        "Nanny.service_binary_name", context=["Platform:Windows"])
  elif platform == test_base.EndToEndTest.Platform.LINUX:
    return config.CONFIG.Get("Client.binary_name", context=["Platform:Linux"])
  elif platform == test_base.EndToEndTest.Platform.DARWIN:
    return config.CONFIG.Get("Client.binary_name", context=["Platform:Darwin"])
  else:
    raise ValueError("Platform %s unknown" % platform)


def GetProcessNameRegex(platform):
  """Returns a regex that matches a process on the client under test."""

  binary = GetProcessName(platform)

  if platform == test_base.EndToEndTest.Platform.WINDOWS:
    # GRRservice.exe -> GRRservice
    binary = binary[:-4]
  elif platform == test_base.EndToEndTest.Platform.LINUX:
    # grrd -> grr
    binary = binary[:-1]
  elif platform == test_base.EndToEndTest.Platform.DARWIN:
    # grr.
    pass
  else:
    raise ValueError("Platform %s unknown" % platform)

  return "^%s*" % binary


class TestYaraScan(test_base.EndToEndTest):
  """YaraScan test."""

  platforms = test_base.EndToEndTest.Platform.ALL

  def runTest(self):

    signature = """
rule test_rule {
  meta:
    desc = "Just for testing."
  strings:
    $s1 = { 31 }
  condition:
    $s1
}
"""

    args = self.grr_api.types.CreateFlowArgs(flow_name="YaraProcessScan")
    args.yara_signature = signature
    args.process_regex = GetProcessNameRegex(self.platform)

    f = self.RunFlowAndWait("YaraProcessScan", args=args)

    results = list(f.ListResults())
    self.assertEqual(len(results), 1)
    yara_result = results[0].payload

    self.assertEqual(len(yara_result.matches), 1)
    match = yara_result.matches[0]

    self.assertEqual(match.process.name, GetProcessName(self.platform))

    self.assertTrue(match.match)

    rules = set()

    for m in match.match:
      # Each hit has some offset + data
      self.assertTrue(m.string_matches)

      for string_match in m.string_matches:
        self.assertEqual(string_match.data, "1")

      rules.add(m.rule_name)

    self.assertEqual(list(rules), ["test_rule"])

    # Ten seconds seems reasonable here, actual values are 0.5s.
    self.assertLess(match.scan_time_us, 10 * 1e6)


class TestYaraProcessDump(test_base.AbstractFileTransferTest):
  """Yara process memory dump test."""

  platforms = test_base.EndToEndTest.Platform.ALL

  def runTest(self):
    args = self.grr_api.types.CreateFlowArgs(flow_name="YaraDumpProcessMemory")
    process_name = GetProcessName(self.platform)
    args.process_regex = GetProcessNameRegex(self.platform)

    f = self.RunFlowAndWait("YaraDumpProcessMemory", args=args)

    results = [x.payload for x in f.ListResults()]
    self.assertGreater(len(results), 1)
    self.assertEqual(len(results[0].dumped_processes), 1)
    self.assertEqual(len(results[0].errors), 0)
    dumped_proc = results[0].dumped_processes[0]

    self.assertEqual(dumped_proc.process.name, process_name)

    paths_to_collect = set(
        [f.path[f.path.find(process_name):] for f in dumped_proc.dump_files])

    dump_file_count = len(dumped_proc.dump_files)
    self.assertGreater(dump_file_count, 0)

    self.assertEqual(len(results), dump_file_count + 1)

    paths_collected = set()
    for dump_file in results[1:]:
      paths_collected.add(
          dump_file.pathspec.path[dump_file.pathspec.path.find(process_name):])

      size = dump_file.st_size
      self.assertTrue(size)

      if size >= 10:
        data = self.ReadFromFile("temp%s" % dump_file.pathspec.path, 10)
        self.assertEqual(len(data), 10)

    self.assertEqual(paths_to_collect, paths_collected)
