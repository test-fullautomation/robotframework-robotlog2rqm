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
# File: robotlog2rqm.py
#
# Initialy created by Tran Duy Ngoan(RBVH/ECM11) / January 2021
#
# This tool is used to parse the robot framework results output.xml
# then import them into RQM - IBM Rational Quality Manager
#
# History:
#
# 2020-01-08:
#  - initial version
#
# ******************************************************************************

import re
import argparse
import os
import sys
import datetime
import colorama as col

from robot.api import ExecutionResult
from RobotLog2RQM.CRQM import CRQMClient
from RobotLog2RQM.version import VERSION, VERSION_DATE

DRESULT_MAPPING = {
   "PASS":  "Passed",
   "FAIL":  "Failed",
   "UNKNOWN": "Inconclusive"
}

DEFAULT_METADATA = {
   "project"      :  "ROBFW",
   "version_sw"   :  "",
   "version_hw"   :  "",
   "version_test" :  "",
   "category"     :  "",

   "testtool"     :  "",
   "configfile"   :  "",
   "tester"       :  "",
   "machine"      :  "",
   "author"       :  "",
   "description"  :  "",

   "component"    :  "unknown",
   "tags"         :  "",
   "team-area"    :  "",
}

#
#  Logger class
#
########################################################################
class Logger():
   """
Logger class for logging message.
   """
   output_logfile = None
   output_console = True
   color_normal   = col.Fore.WHITE + col.Style.NORMAL
   color_error    = col.Fore.RED + col.Style.BRIGHT
   color_warn     = col.Fore.YELLOW + col.Style.BRIGHT
   color_reset    = col.Style.RESET_ALL + col.Fore.RESET + col.Back.RESET
   prefix_warn    = "WARN: "
   prefix_error   = "ERROR: "
   prefix_fatalerror = "FATAL ERROR: "
   prefix_all = ""
   dryrun = False

   @classmethod
   def config(cls, output_console=True, output_logfile=None, dryrun=False):
      """
Configure Logger class.

**Arguments:**

*  ``output_console``

   / *Condition*: optional / *Type*: bool / *Default*: True /

   Write message to console output.

*  ``output_logfile``

   / *Condition*: optional / *Type*: str / *Default*: None /

   Path to log file output.

*  ``dryrun``

   / *Condition*: optional / *Type*: bool / *Default*: True /

   If set, a prefix as 'dryrun' is added for all messages.

**Returns:**

(*no returns*)
      """
      cls.output_console = output_console
      cls.output_logfile = output_logfile
      cls.dryrun = dryrun
      if cls.dryrun:
         cls.prefix_all = cls.color_warn + "DRYRUN  " + cls.color_reset

   @classmethod
   def log(cls, msg='', color=None, indent=0):
      """
Write log message to console/file output.

**Arguments:**

*  ``msg``

   / *Condition*: optional / *Type*: str / *Default*: '' /

   Message which is written to output.

*  ``color``

   / *Condition*: optional / *Type*: str / *Default*: None /

   Color style for the message.

*  ``indent``

   / *Condition*: optional / *Type*: int / *Default*: 0 /

   Offset indent.

**Returns:**

(*no returns*)
      """
      if color==None:
         color = cls.color_normal
      if cls.output_console:
         print(cls.prefix_all + cls.color_reset + color + " "*indent + msg + cls.color_reset)
      if cls.output_logfile!=None and os.path.isfile(cls.output_logfile):
         with open(cls.output_logfile, 'a') as f:
            f.write(" "*indent + msg)
      return

   @classmethod
   def log_warning(cls, msg):
      """
Write warning message to console/file output.

**Arguments:**

*  ``msg``

   / *Condition*: required / *Type*: str /

   Warning message which is written to output.

**Returns:**

(*no returns*)
      """
      cls.log(cls.prefix_warn+str(msg), cls.color_warn)

   @classmethod
   def log_error(cls, msg, fatal_error=False):
      """
Write error message to console/file output.

*  ``msg``

   / *Condition*: required / *Type*: str /

   Error message which is written to output.

*  ``fatal_error``

   / *Condition*: optional / *Type*: bool / *Default*: False /

   If set, tool will terminate after logging error message.

**Returns:**

(*no returns*)
      """
      prefix = cls.prefix_error
      if fatal_error:
         prefix = cls.prefix_fatalerror

      cls.log(prefix+str(msg), cls.color_error)
      if fatal_error:
         cls.log(f"{sys.argv[0]} has been stopped!", cls.color_error)
         exit(1)


def get_from_tags(lTags, reInfo):
   """
Extract testcase information from tags.

Example:
   TCID-xxxx, FID-xxxx, ...

**Arguments:**

*  ``lTags``

   / *Condition*: required / *Type*: list /

   List of tag information.

*  ``reInfo``

   / *Condition*: required / *Type*: str /

   Regex to get the expectated info (ID) from tag info.

**Returns:**

*  ``lInfo``

   / *Type*: list /

   List of expected information (ID)
   """
   lInfo = []
   if len(lTags) != 0:
      for tag in lTags:
         oMatch = re.search(reInfo, tag, re.I)
         if oMatch:
            lInfo.append(oMatch.group(1))
   return lInfo

def convert_to_datetime(time):
   """
Convert time string to datetime.

**Arguments:**

*  ``time``

   / *Condition*: required / *Type*: str /

   String of time.

**Returns:**

*  ``dt``

   / *Type*: `datetime` object/

   Datetime object.
   """
   tp=re.findall(r"(\d{4})(\d{2})(\d{2})\s(\d+):(\d+):(\d+)\.(\d+)",time)[0]
   tp=list(map(int,tp))
   dt=datetime.datetime(tp[0],tp[1],tp[2],tp[3],tp[4],tp[5],tp[6])
   return dt

def __process_commandline():
   """
Process provided argument(s) from command line.

Avalable arguments in command line:
   - `-v`, `--version` : tool version information.
   - `resultxmlfile` : path to the xml result file or directory of result files to be imported.
   - `host` : RQM host url.
   - `project` : RQM project name.
   - `user` : user for RQM login.
   - `password` : user password for RQM login.
   - `testplan` : RQM testplan ID.
   - `--recursive` : if True, then the path is searched recursively for log files to be imported.
   - `--createmissing` : if True, then all testcases without tcid are created when importing.
   - `--dryrun` : if True, then verify all input arguments (includes RQM authentication) and show what would be done.

**Arguments:**

(*no arguments*)

**Returns:**

   / *Type*: `ArgumentParser` object /

   ArgumentParser object.
   """
   PROG_NAME = "RobotLog2RQM (RobotXMLResult to RQM importer)"
   PROG_DESC = "RobotLog2RQM imports XML result files (default: output.xml) "+\
               "generated by the Robot Framework into an IBM Rational Quality Manager."

   cmdParser=argparse.ArgumentParser(prog=PROG_NAME, description=PROG_DESC)

   cmdParser.add_argument('-v', '--version', action='version',
                          version=f'v{VERSION} ({VERSION_DATE})',
                          help='Version of the RobotLog2RQM importer.')
   cmdParser.add_argument('resultxmlfile', type=str,
                          help='absolute or relative path to the xml result file or directory of result files to be imported.')
   cmdParser.add_argument('host', type=str, help='RQM host url.')
   cmdParser.add_argument('project', type=str, help='project on RQM.')
   cmdParser.add_argument('user', type=str, help='user for RQM login.')
   cmdParser.add_argument('password', type=str, help='password for RQM login.')
   cmdParser.add_argument('testplan', type=str,
                          help='testplan ID for this execution.')
   cmdParser.add_argument('--recursive',action="store_true",
                          help='if set, then the path is searched recursively for log files to be imported.')
   cmdParser.add_argument('--createmissing', action="store_true",
                          help='if set, then all testcases without tcid are created when importing.')
   cmdParser.add_argument('--updatetestcase', action="store_true",
                          help='if set, then testcase information on RQM will be updated bases on robot testfile.')
   cmdParser.add_argument('--dryrun',action="store_true",
                          help='if set, then verify all input arguments (includes RQM authentication) and show what would be done.')

   return cmdParser.parse_args()

def process_suite_metadata(suite, default_metadata=DEFAULT_METADATA):
   """
Try to find metadata information from all suite levels.

Metadata at top suite level has a highest priority.

**Arguments:**

*  ``suite``

   / *Condition*: required / *Type*: `TestSuite` object /

   Robot suite object.

*  ``default_metadata``

   / *Condition*: optional / *Type*: dict / *Default*: DEFAULT_METADATA /

   Initial Metadata information for updating.

**Returns:**

*  ``dMetadata``

   / *Type*: dict /

   Dictionary of Metadata information.
   """
   dMetadata = dict(default_metadata)
   # Try to get metadata from first child of suite - multiple log files
   if suite.suites != None and len(list(suite.suites)) > 0:
      dMetadata = process_suite_metadata(suite.suites[0], dMetadata)
   # The higher suite level metadata have higher priority
   if suite.metadata != None:
      dMetadata = process_metadata(suite.metadata, dMetadata)

   return dMetadata

def process_metadata(metadata, default_metadata=DEFAULT_METADATA):
   """
Extract metadata from suite result bases on DEFAULT_METADATA.

**Arguments:**

*  ``metadata``

   / *Condition*: required / *Type*: dict /

   Robot metadata object.

*  ``default_metadata``

   / *Condition*: optional / *Type*: dict / *Default*: DEFAULT_METADATA /

   Initial Metadata information for updating.

**Returns:**

*  ``dMetadata``

   / *Type*: dict /

   Dictionary of Metadata information.
   """
   dMetadata = dict(default_metadata)
   for key in dMetadata.keys():
      if key in metadata:
         if metadata[key] != None:
            dMetadata[key] = metadata[key]

   return dMetadata

def process_suite(RQMClient, suite):
   """
Process robot suite for importing to RQM.

**Arguments:**

*  ``RQMClient``

   / *Condition*: required / *Type*: `RQMClient` object/

   RQMClient object.

*  ``suite``

   / *Condition*: required / *Type*: `TestSuite` object/

   Robot suite object.

**Returns:**

(*no returns*)
   """
   if len(list(suite.suites)) > 0:
      for subsuite in suite.suites:
         process_suite(RQMClient, subsuite)
   else:
      Logger.log(f"Process suite: {suite.name}")

      # update missing metadata from parent suite
      if suite.parent and suite.parent.metadata:
         for key in suite.parent.metadata.keys():
            if key not in suite.metadata:
               suite.metadata[key] = suite.parent.metadata[key]

      if len(list(suite.tests)) > 0:
         for test in suite.tests:
            process_test(RQMClient, test)

def process_test(RQMClient, test):
   """
Process robot test for importing to RQM.

**Arguments:**

*  ``RQMClient``

   / *Condition*: required / *Type*: `RQMClient` object/

   RQMClient object.

*  ``test``

   / *Condition*: required / *Type*: `TestCase` object/

   Robot test object.

**Returns:**

(*no returns*)
   """
   Logger.log(f"Process test: {test.name}")

   # Avoid create resources with dryrun
   if Logger.dryrun:
      return

   # Parse test case data:
   _tc_fid = ";".join(get_from_tags(test.tags, "fid-(.+)"))
   lTCIDTags = get_from_tags(test.tags, "tcid-(.+)")
   _tc_id = ";".join(lTCIDTags)
   _tc_link = ";".join(get_from_tags(test.tags, "robotfile-(.+)"))

   # from metadata
   metadata_info = process_metadata(test.parent.metadata)
   _tc_machine = metadata_info['machine']
   _tc_account = metadata_info['tester']
   _tc_cmpt    = metadata_info['component']
   _tc_team    = metadata_info['team-area']
   # from RQMClient
   _tc_testplan_id = RQMClient.testplan
   _tc_config_id   = RQMClient.configuration
   _tc_build_id    = RQMClient.build
   _tc_createmissing = RQMClient.createmissing
   _tc_update = RQMClient.updatetestcase
   # from robot result object
   _tc_name = test.name
   _tc_desc = test.doc
   try:
      _tc_result = DRESULT_MAPPING[test.status]
   except Exception:
      Logger.log_error(f"Invalid Robotframework result state '{test.status}' of test '{_tc_name}'.")
      return
   _tc_message = test.message
   _tc_start_time = convert_to_datetime(test.starttime)
   _tc_end_time = convert_to_datetime(test.endtime)
   _tc_duration = _tc_end_time - _tc_start_time
   _tc_duration = int(_tc_duration.total_seconds())

   # Verify the tcid is provided or not
   if _tc_id == "":
      # If --createmissing is set. Test case without tcid will be created on RQM:
      # Create new testcase template
      # Create new testcase on RQM
      # Update dMappingTCID (to update *.robot testfile with generated ID - Not implemented yet).
      if _tc_createmissing:
         oTCTemplate = RQMClient.createTestcaseTemplate( _tc_name,
                                                         _tc_desc,
                                                         _tc_cmpt,
                                                         _tc_fid,
                                                         _tc_team,
                                                         _tc_link)
         res = RQMClient.createResource('testcase', oTCTemplate)
         if res['success']:
            _tc_id = res['id']
            Logger.log(f"Create testcase '{_tc_name}' with ID '{_tc_id}' successfully!")
            RQMClient.dMappingTCID[_tc_id] = _tc_name
         else:
            Logger.log_error(f"Create testcase '{_tc_name}' failed. Reason: {res['message']}")
            return
      else:
         Logger.log_error(f"There is no 'tcid' information for importing test '{_tc_name}'.")
         return
   else:
      # If more than 1 tcid are defined in [Tags], the first one is used.
      if len(lTCIDTags) > 1:
         _tc_id = lTCIDTags[0]
         Logger.log_warning(f"More than 1 'tcid-' tags in test '{_tc_name}', '{_tc_id}' is used.")

      # If --updatetestcase is set. Test case with provided tcid will be updated on RQM:
      # Get existing resource of testcase from RQM.
      # Update information in testcase xml template.
      # Update the existing testcase resource with the new one on RQM.
      if _tc_update:
         resTC = RQMClient.getResourceByID('testcase', _tc_id)
         if resTC.status_code == 200 and resTC.text:
            oTCTemplate = RQMClient.createTestcaseTemplate( _tc_name,
                                                            _tc_desc,
                                                            _tc_cmpt,
                                                            _tc_fid,
                                                            _tc_team,
                                                            _tc_link,
                                                            sTCtemplate=str(resTC.text))
            RQMClient.updateResourceByID('testcase', _tc_id, oTCTemplate)
            Logger.log(f"Update testcase '{_tc_name}' with ID '{_tc_id}' successfully!")
         else:
            Logger.log_error(f"Update testcase with ID '{_tc_id}' failed. Please check whether it is existing on RQM.")
            return

   # Create TCER:
      # Template
      # Upload
      # Append lTCERIDs (for linking testsuite result)
   oTCERTemplate = RQMClient.createTCERTemplate( _tc_id,
                                                 _tc_name,
                                                 _tc_testplan_id,
                                                 _tc_config_id,
                                                 _tc_team)
   res = RQMClient.createResource('executionworkitem', oTCERTemplate)
   _tc_tcer_id = res['id']
   if res['success']:
      Logger.log(f"Created TCER with ID '{_tc_tcer_id}' successfully.")
   elif (res['status_code'] == 303 or res['status_code'] == 200) and res['id'] != '':
      Logger.log_warning(f"TCER for testcase '{_tc_id}' and testplan '{_tc_testplan_id}' is existing with ID: '{_tc_tcer_id}'")
   else:
      Logger.log_error(f"Create TCER failed. Please check whether test case with ID '{_tc_id}' is existing on RQM or not. Reason: {res['message']}.")
      return

   if _tc_tcer_id not in RQMClient.lTCERIDs:
      RQMClient.lTCERIDs.append(_tc_tcer_id)

   # Create executionresult:
      # Template
      # Upload
      # Append lTCResultIDs (for linking testsuite result)
   oTCResultTemplate = RQMClient.createExecutionResultTemplate( _tc_id,
                                                                _tc_name,
                                                                _tc_testplan_id,
                                                                _tc_tcer_id,
                                                                _tc_result,
                                                                _tc_start_time,
                                                                _tc_end_time,
                                                                _tc_duration,
                                                                _tc_machine,
                                                                _tc_account,
                                                                _tc_message,
                                                                _tc_build_id,
                                                                _tc_team)
   res = RQMClient.createResource('executionresult', oTCResultTemplate)
   if res['success']:
      Logger.log(f"Create result for test '{_tc_name}' successfully!")
      _tc_result_id = res['id']
   else:
      Logger.log_error(f"Create result for test '{_tc_name}' failed. Reason: {res['message']}.")
      return
   if _tc_result_id not in RQMClient.lTCResultIDs:
      RQMClient.lTCResultIDs.append(_tc_result_id)

   # Append lTestcaseIDs (for linking testplan/testsuite)
   if _tc_id not in RQMClient.lTestcaseIDs:
      RQMClient.lTestcaseIDs.append(_tc_id)

def RobotLog2RQM(args=None):
   """
Import robot results from output.xml to RQM - IBM Rational Quality Manager.

Flow to import Robot results to RQM:

1. Process provided arguments from command line
2. Login Rational Quality Management (RQM)
3. Parse Robot results
4. Import results into RQM
5. Link all executed testcases to provided testplan/testsuite ID

**Arguments:**

*  ``args``

   / *Condition*: required / *Type*: `ArgumentParser` object /

   Argument parser object which contains:

   * `resultxmlfile` : path to the xml result file or directory of result files to be imported.
   * `host` : RQM host url.
   * `project` : RQM project name.
   * `user` : user for RQM login.
   * `password` : user password for RQM login.
   * `testplan` : RQM testplan ID.
   * `recursive` : if True, then the path is searched recursively for log files to be imported.
   * `createmissing` : if True, then all testcases without tcid are created when importing.
   * `updatetestcase` : if True, then testcases information on RQM will be updated bases on robot testfile.
   * `dryrun` : if True, then verify all input arguments (includes RQM authentication) and show what would be done.

**Returns:**

(*no returns*)
   """

   # 1. process provided arguments from command line as default
   args = __process_commandline()
   Logger.config(dryrun=args.dryrun)

   # 2. Parse Robot results
   sLogFileType="NONE"
   if os.path.exists(args.resultxmlfile):
      sLogFileType="PATH"
      if os.path.isfile(args.resultxmlfile):
         sLogFileType="FILE"
   else:
      Logger.log_error(f"Given resultxmlfile is not existing: '{args.resultxmlfile}'.", fatal_error=True)

   listEntries=[]
   if sLogFileType=="FILE":
      listEntries.append(args.resultxmlfile)
   else:
      if args.recursive:
         Logger.log("Searching *.xml result files recursively...")
         for root, _, files in os.walk(args.resultxmlfile):
            for file in files:
               if file.endswith(".xml"):
                  listEntries.append(os.path.join(root, file))
                  Logger.log(os.path.join(root, file), indent=2)
      else:
         Logger.log("Searching *.xml result files...")
         for file in os.listdir(args.resultxmlfile):
            if file.endswith(".xml"):
               listEntries.append(os.path.join(args.resultxmlfile, file))
               Logger.log(os.path.join(args.resultxmlfile, file), indent=2)

      # Terminate tool with error when no result file under provided resultxmlfile folder
      if len(listEntries) == 0:
         Logger.log_error(f"No *.xml result file under '{args.resultxmlfile}' folder.", fatal_error=True)

   sources = tuple(listEntries)
   result = ExecutionResult(*sources)
   result.configure()

   # 3. Login Rational Quality Management (RQM)
   RQMClient = CRQMClient(args.user, args.password, args.project, args.host)
   try:
      bSuccess = RQMClient.login()
      if bSuccess:
         Logger.log(f"Login RQM as user '{args.user}' successfully!")
      else:
         Logger.log_error("Could not login to RQM: 'Unkown reason'.")
   except Exception as reason:
      Logger.log_error(f"Could not login to RQM: '{str(reason)}'.")

   # 4. Import results into RQM
   try:
      metadata_info = process_suite_metadata(result.suite)
      if not metadata_info['version_sw']:
         metadata_info['version_sw'] = None
      if not metadata_info['project']:
         metadata_info['project'] = None
      # Avoid create build and configuration in dryrun, just verify the testplan
      if args.dryrun:
         metadata_info['version_sw'] = None
         metadata_info['project'] = None
      RQMClient.config(args.testplan, metadata_info['version_sw'],
                    metadata_info['project'], args.createmissing, args.updatetestcase)
      # Process suite for importing
      process_suite(RQMClient, result.suite)

      # Link all imported testcase ID(s) with testplan
      Logger.log("Linking all imported testcase ID(s) with testplan ...")
      RQMClient.linkListTestcase2Testplan(args.testplan)

      # Update testcase(s) with generated ID(s)
      # Under developing

   except Exception as reason:
      Logger.log_error(f"Could not import results to RQM. Reason: {reason}", fatal_error=True)

   # 5. Disconnect from RQM
   RQMClient.disconnect()
   Logger.log("All test results have been imported to RQM successfully.!")

if __name__=="__main__":
   RobotLog2RQM()
