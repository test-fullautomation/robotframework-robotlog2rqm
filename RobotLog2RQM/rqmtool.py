#  Copyright 2020-2023 Robert Bosch GmbH
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ******************************************************************************
#
# File: rqmtool.py
#
# Initially created by Tran Duy Ngoan(RBVH/EMC51) / October 2025
#
# This tool is used to fetch RQM resources
#
# History:
#
# 2025-10-20:
#  - initial version
#
# ******************************************************************************

import argparse
import os
import csv
import json
import base64

from RobotLog2RQM.CRQM import CRQMClient
from RobotLog2RQM.logger import Logger
from RobotLog2RQM.version import VERSION, VERSION_DATE

OUTPUT_FORMATS = ['json', 'csv']
ARTIFACT_TYPES = ['testcase', 'testsuite']

def __process_commandline():
   """
Process provided argument(s) from command line.

**Arguments:**

(*no arguments*)

**Returns:**

   / *Type*: `ArgumentParser` object /

   ArgumentParser object.
   """
   parser = argparse.ArgumentParser(
      prog="RQMTool",
      description="Fetch RQM resources."
   )

   parser.add_argument(
      '-v', '--version',
      action='version',
      version=f'v{VERSION} ({VERSION_DATE})',
      help='Version of the RQMTool.'
   )
   parser.add_argument(
      "--host",
      required=True,
      help="RQM server URL."
   )
   parser.add_argument(
      "--project",
      required=True,
      help="RQM project."
   )
   parser.add_argument(
      "--user",
      required=True,
      help="RQM username."
   )
   # exclusive group to provide only --password, --password-enc or --password-file
   group_password = parser.add_mutually_exclusive_group(required=True)
   group_password.add_argument(
      "--password",
      help="RQM password."
   )
   group_password.add_argument(
      "--password-enc",
      help="RQM password as base64-encoded string."
   )
   group_password.add_argument(
      "--password-file",
      help="Path to a file containing the password. If the content starts with 'b64:', "
           "the remainder is treated as base64-encoded."
   )
   # exclusive group to provide only --testsuite or --testplan
   group = parser.add_mutually_exclusive_group(required=True)
   group.add_argument(
      "--testplan",
      help="RQM testplan ID."
   )
   group.add_argument(
      "--testsuite",
      help="RQM testsuite ID."
   )
   parser.add_argument(
      "--stream",
      type=str,
      help="project stream. Note, requires Configuration Management (CM) to be enabled for the project area."
   )
   parser.add_argument(
      '--baseline',
      type=str,
      help='project baseline. Note, requires Configuration Management (CM), or Baselines Only to be enabled for the project area.'
   )
   parser.add_argument(
      "--dryrun",
      action="store_true",
      help='if set, then verify all input arguments (includes RQM authentication) and show what would be done.')
   parser.add_argument(
      "--format",
      default="csv",
      choices=OUTPUT_FORMATS,
      help="Output format (csv or json). Default is csv.")
   parser.add_argument(
      "--types",
      default="testcase,testsuite",
      help="Comma-separated list of artifact types to fetch. Allowed: testcase, testsuite.")
   parser.add_argument(
      "--output-dir",
      default=".",
      help="Directory to save output files.")
   parser.add_argument(
      "--basename",
      default="testplan_export",
      help="Base name for output files.")
   return parser.parse_args()

def __resolve_password(args):
   """
Resolve password from --password-enc, --password-file, or --password.
Order of precedence: password-enc > password-file > password.
   """
   if args.password_enc:
      try:
         return base64.b64decode(args.password_enc).decode("utf-8")
      except Exception as e:
         raise ValueError(f"Failed to decode --password-enc: {e}")

   if args.password_file:
      if not os.path.isfile(args.password_file):
         raise FileNotFoundError(f"Password file not found: {args.password_file}")
      with open(args.password_file, "r", encoding="utf-8") as f:
         content = f.read().strip()
      # If file content starts with 'b64:', decode the remainder
      if content.startswith("b64:"):
         enc = content[4:]
         try:
            return base64.b64decode(enc).decode("utf-8")
         except Exception as e:
            raise ValueError(f"Failed to decode base64 in password file: {e}")
      return content

   if args.password:
      return args.password

   raise ValueError("No password provided. Use --password-enc, --password-file, or --password.")

def __validate_arguments(arguments):
   """
Validate and normalize command line arguments.

**Arguments:**

*  ``arguments``

   / *Condition*: required / *Type*: `ArgumentParser` object  /

   Parsed arguments from __process_commandline().

**Returns:**

*  ``arguments``

   / *Type*: `ArgumentParser` object /

   ArgumentParser object.
   """
   artifact_types = arguments.types
   if isinstance(artifact_types, str):
      artifact_types = [x.strip().lower() for x in artifact_types.split(',')]
   elif isinstance(artifact_types, (list, tuple)):
      artifact_types = [x.lower() for x in artifact_types]
   else:
      raise TypeError(f"Invalid type for '--types': {type(artifact_types).__name__}, expected str or list.")

   for t in artifact_types:
      if t not in ARTIFACT_TYPES:
         raise ValueError(
               f"Invalid artifact type '{t}'. Allowed: {', '.join(ARTIFACT_TYPES)}."
         )
   arguments.types = artifact_types

   return arguments

def write_json_file(file_name, data):
   """
Write data to a JSON file.

**Arguments:**

*  ``file_name``

   / *Condition*: required / *Type*: str /

   Path of the JSON file to write.

*  ``data``

   / *Condition*: required / *Type*: dict /

   Data to export.

**Returns:**

(*no returns*)
   """
   with open(file_name, 'w', encoding='utf-8') as f:
      json.dump(data, f, indent=2, ensure_ascii=False)
   Logger.log(f"Exported data to: {file_name}")

def write_csv_file(file_name, data, artifact_type):
   """
Write data to a CSV file for a specific artifact type.

**Arguments:**

*  ``file_name``

   / *Condition*: required / *Type*: str /

   Path of the CSV file to write.

*  ``data``

   / *Condition*: required / *Type*: dict /

   Data dictionary containing artifacts.

* ``artifact_type``

   / *Condition*: required / *Type*: str /

   Artifact type (`testcase` or `testsuite`) to export.

**Returns:**

(*no returns*)
   """
   artifact_data = data.get(artifact_type, [])
   if not artifact_data:
      Logger.log_warning(f"No data for '{artifact_type}', skipping CSV export.")
      return

   fieldnames = list(data[artifact_type][0].keys()) if data[artifact_type] else ["id", "name"]
   with open(file_name, mode="w", newline='', encoding="utf-8") as f:
      writer = csv.DictWriter(f, fieldnames=fieldnames)
      writer.writeheader()
      for row in data[artifact_type]:
         writer.writerow(row)
   Logger.log(f"Exported {artifact_type} to: {file_name}")

def write_output_file(data, output_dir=".", basename="testplan_export", extension="csv", artifact_types=None):
   """
Write data to output files (JSON or CSV) according to specified options.

**Arguments:**

*  ``data``

   / *Condition*: required / *Type*: dict /

   Data dictionary containing artifacts.

*  ``output_dir``

   / *Condition*: optional / *Type*: str /

   Directory to save output files. Default is current directory.

*  ``basename``

   / *Condition*: optional / *Type*: str /

   Base name for output files. Default is "testplan_export".

*  ``extension``

   / *Condition*: optional / *Type*: str /

   Output format: `json` or `csv`. Default is `csv`.

*  ``artifact_types``

   / *Condition*: optional / *Type*: list /

   Artifact types to export. Default is all supported types.

**Returns:**

(*no returns*)
   """
   if extension == 'json':
      file_name = os.path.join(output_dir, f"{basename}.json")
      write_json_file(file_name, data)
   else:
      # CSV export: one file per artifact_type
      for artifact_type in (artifact_types or ARTIFACT_TYPES):
         file_name = os.path.join(output_dir, f"{basename}_{artifact_type}s.csv")
         write_csv_file(file_name, data, artifact_type)

def normalize_custom_attributes(data, artifact_types):
   """
Ensure all artifacts across projects have consistent keys.
Missing custom attributes will be filled with empty strings.

**Arguments:**

*  ``data``

   / *Condition*: required / *Type*: dict /

   Dictionary containing artifact data fetched from RQM, where each key represents
   an artifact type (e.g., ``testcase``, ``testsuite``) and the value is a list
   of dictionaries holding artifact details.

*  ``artifact_types``

   / *Condition*: required / *Type*: list /

   List of artifact types to process (e.g., ``['testcase', 'testsuite']``).
   Each type key in ``data`` will be normalized to ensure all items have the same set of attributes.

**Returns:**

*  ``data``

   / *Type*: dict /

   Normalized dictionary with consistent keys across all artifacts.
   Any missing custom attributes are added with an empty string ("") as value.
   """
   for artifact_type in artifact_types:
      artifacts = data.get(artifact_type, [])
      if not artifacts:
         continue

      # Collect all keys (standard + custom attributes)
      all_keys = set()
      for item in artifacts:
         all_keys.update(item.keys())

      # Fill missing attributes with empty string
      for item in artifacts:
         for key in all_keys:
               if key not in item:
                  item[key] = ""

   return data


def RQMTool():
   """
Main entry point for RQMTool CLI.

**Arguments:**

(*no arguments*)

**Returns:**

(*no returns*)
   """
   args = __process_commandline()
   __validate_arguments(args)
   Logger.config(dryrun=args.dryrun)

   # Resolve password securely (supports base64 and file-based)
   try:
      resolved_password = __resolve_password(args)
   except Exception as reason:
      Logger.log_error(f"Could not resolve password: '{str(reason)}'.")
      return

   RQMClient = CRQMClient(args.user, resolved_password, args.project, args.host)
   try:
      bSuccess = RQMClient.login()
      RQMClient.config(stream=args.stream, baseline=args.baseline)
      if bSuccess:
         Logger.log()
         Logger.log(f"Login RQM as user '{args.user}' successfully!")
      else:
         Logger.log_error("Could not login to RQM: 'Unknown reason'.")
   except Exception as reason:
      Logger.log_error(f"Could not login to RQM: '{str(reason)}'.")

   if not args.dryrun:
      if args.testplan:
         artifact_types = args.types
         basename_with_id = f"{args.basename}_{args.testplan}"
         test_data = RQMClient.getTestArtifactsFromResource('testplan', args.testplan, args.types)
         test_data = normalize_custom_attributes(test_data, artifact_types)
      elif args.testsuite:
         artifact_types = ['testcase']
         if args.basename == "testplan_export":
            basename_with_id = f"testsuite_export_{args.testsuite}"
         else:
            basename_with_id = f"{args.basename}_{args.testsuite}"
         test_data = RQMClient.getTestArtifactsFromResource('testsuite', args.testsuite, artifact_types)
         test_data = normalize_custom_attributes(test_data, artifact_types)

      write_output_file(
         test_data,
         output_dir=args.output_dir,
         basename=basename_with_id,
         extension=args.format,
         artifact_types=artifact_types
      )

      for artifact_type in artifact_types:
         items = test_data.get(artifact_type, [])
         Logger.log(f"Found {len(items)} {artifact_type}(s)")
         cnt = 1
         for item in items:
            Logger.log(f"{cnt:>3}. {item['id']} - {item['name']}", indent=2)
            cnt += 1

if __name__ == "__main__":
   RQMTool()