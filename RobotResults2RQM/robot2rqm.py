#  Copyright 2020-2022 Robert Bosch Car Multimedia GmbH
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
# File: robot2rqm.py
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
import base64
import argparse
import os
import sys
import datetime
import time
import colorama as col

from robot.api import ExecutionResult
from RobotResults2RQM.CRQM import CRQMClient
from RobotResults2RQM.version import VERSION, VERSION_DATE

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
   "author"       :  "",
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
   def config(cls, output_console=True, output_logfile=None, indent=0, 
              dryrun=False):
      """
      Configure Logger class.

      Args:
         output_console : write message to console output.

         output_logfile : path to log file output.

         indent : offset indent.

         dryrun : if set, a prefix as 'dryrun' is added for all messages.

      Returns:
         None.
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

      Args:
         msg : message to write to output.

         color : color style for the message.

         indent : offset indent.
      
      Returns:
         None.
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
      
      Args:
         msg : message to write to output.

      Returns:
         None.
      """
      cls.log(cls.prefix_warn+str(msg), cls.color_warn)

   @classmethod
   def log_error(cls, msg, fatal_error=False):
      """
      Write error message to console/file output.

      Args:
         msg : message to write to output.

         fatal_error : if set, tool will terminate after logging error message.

      Returns:
         None.
      """
      prefix = cls.prefix_error
      if fatal_error:
         prefix = cls.prefix_fatalerror

      cls.log(prefix+str(msg), cls.color_error)
      if fatal_error:
         cls.log("%s has been stopped!"%(sys.argv[0]), cls.color_error)
         exit(1)


def get_from_tags(lTags, reInfo):
   """
      Extract testcase information from tags.

      Example: 
         TCID-xxxx, FID-xxxx, ...

      Args:
         lTags : list of tag information.

         reInfo : regex to get the expectated info (ID) from tag info.

      Returns:
         lInfo : list of expected information (ID)
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

   Args:
      time : string of time.

   Returns:
      dt : datetime object
   """
   tp=re.findall("(\d{4})(\d{2})(\d{2})\s(\d+):(\d+):(\d+)\.(\d+)",time)[0]
   tp=list(map(int,tp))
   dt=datetime.datetime(tp[0],tp[1],tp[2],tp[3],tp[4],tp[5],tp[6])
   return dt 

def __process_commandline():
   """
   process provided argument(s) from command line.

   Avalable arguments in command line:
      - `-v` : tool version information.
      - `outputfile` : path to the output file or directory with output files to be imported.
      - `host` : RQM host url.
      - `project` : RQM project name.
      - `user` : user for RQM login.
      - `password` : user password for RQM login.
      - `testplan` : RQM testplan ID.
      - `-recursive` : if True, then the path is searched recursively for log files to be imported.
      - `-createmissing` : if True, then all testcases without fcid are created when importing.
      - `-dryrun` : if True, then just check the RQM authentication and show what would be done.

   Returns:
      ArgumentParser object.
   """
   cmdlineparser=argparse.ArgumentParser(prog="RobotResults2RQM (XMLoutput to RQM importer)", 
                                       description="RobotResults2RQM imports XML output files (default: output.xml) " + \
                                                   "generated by the Robot Framework into a IBM Rational Quality Manager."
                                       )

   cmdlineparser.add_argument('-v',action='version', version=f'v{VERSION} ({VERSION_DATE})',help='Version of the RobotResults2RQM importer.')
   cmdlineparser.add_argument('outputfile', type=str, help='absolute or relative path to the output file or directory with output files to be imported.')
   cmdlineparser.add_argument('host', type=str, help='RQM host url.')
   cmdlineparser.add_argument('project', type=str, help='project on RQM.')
   cmdlineparser.add_argument('user', type=str, help='user for RQM login.')
   cmdlineparser.add_argument('password', type=str, help='password for RQM login.')
   cmdlineparser.add_argument('testplan', type=str, help='testplan ID for this execution.')
   cmdlineparser.add_argument('-recursive',action="store_true", help='if set, then the path is searched recursively for log files to be imported.')
   cmdlineparser.add_argument('-createmissing', action="store_true", help='if set, then all testcases without fcid are created when importing.')
   cmdlineparser.add_argument('-updatetestcase', action="store_true", help='if set, then testcase information on RQM will be updated bases on robot testfile.')
   cmdlineparser.add_argument('-dryrun',action="store_true", help='if set, then just show what would be done.')
   # cmdlineparser.add_argument('-testsuite',type=str, help='testsuite ID for this execution.')
   # cmdlineparser.add_argument('-syncfid', action="store_true", help='update FID information from TML test cases to RQM.')
   # cmdlineparser.add_argument('-syncnewtc', action="store_true", help='sync information of new test cases (created on RQM but TML file attribute is empty) from TML to RQM.')
   return cmdlineparser.parse_args()

def process_suite_metadata(suite, default_metadata=DEFAULT_METADATA):
   """
   Try to find metadata information from all suite levels.
   
   Note:
      Metadata at top suite level has a highest priority.
   
   Args:
      suite :  Robot suite object.

      default_metadata: initial Metadata information for updating.

   Returns:
      dMetadata : dictionary of Metadata information.
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
   Extract metadata from suite result bases on DEFAULT_METADATA

   Args:
      metadata :  Robot metadata object.

      default_metadata: initial Metadata information for updating.

   Returns:
      dMetadata : dictionary of Metadata information.   
   """
   dMetadata = dict(default_metadata)
   for key in dMetadata.keys():
      if key in metadata:
         if metadata[key] != None:
            dMetadata[key] = metadata[key]

   return dMetadata

def process_suite(RQMClient, suite):
   """
   process robot suite for importing to RQM.

   Args:
      RQMClient :  RQMClient object.

      suite : Robot suite object.

   Returns:
      None.   
   """
   if len(list(suite.suites)) > 0:
      for subsuite in suite.suites:
         process_suite(RQMClient, subsuite)
   else:
      Logger.log("Process suite: %s"%suite.name)

      # update missing metadata from parent suite
      if suite.parent and suite.parent.metadata:
         for key in suite.parent.metadata.keys():
            if key not in suite.metadata:
               suite.metadata[key] = suite.parent.metadata[key]
      
      # Create testsuite
      # Create TSER
      if len(list(suite.tests)) > 0:
         for test in suite.tests:
            process_test(RQMClient, test)
      # Create testsuite result

def process_test(RQMClient, test):
   """
   process robot test for importing to RQM.

   Args:
      RQMClient :  RQMClient object.

      test : Robot test object.

   Returns:
      None.   
   """
   Logger.log("Process test: %s"%test.name)

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
   except Exception as reason:
      Logger.log_error("Invalid Robotframework result state '%s' of test '%s'."%(test.status,_tc_name))
      return
   _tc_message = test.message
   _tc_start_time = convert_to_datetime(test.starttime)
   _tc_end_time = convert_to_datetime(test.endtime)
   _tc_duration = _tc_end_time - _tc_start_time
   _tc_duration = int(_tc_duration.total_seconds())

   # Verify the tcid is provided or not
   if _tc_id == "":
      # If -createmissing is set. Test case without tcid will be created on RQM:
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
            Logger.log("Create testcase '%s' with id %s successfully!"%(_tc_name, _tc_id))
            RQMClient.dMappingTCID[_tc_id] = _tc_name
         else:
            Logger.log_error("Create testcase '%s' failed. Reason: %s"%(_tc_name, res['message']))
            return
      else:
         Logger.log_error("There is no 'tcid' information for importing test '%s'."%_tc_name)
         return
   else:
      # If more than 1 tcid are defined in [Tags], the first one is used.
      if len(lTCIDTags) > 1:
         _tc_id = lTCIDTags[0]
         Logger.log_warning("More than 1 'tcid-' tags in test '%s', use id '%s'."%(_tc_name, _tc_id))

      # If -updatetestcase is set. Test case with provided tcid will be updated on RQM:
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
            Logger.log("Update testcase '%s' with id %s successfully!"%(_tc_name, _tc_id))
         else:
            Logger.log_error("Update testcase with ID '%s' failed. Please check whether it is existing on RQM."%_tc_id)
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
      Logger.log('Created TCER with id %s successfully.'%_tc_tcer_id)
   elif (res['status_code'] == 303 or res['status_code'] == 200) and res['id'] != '':
      Logger.log_warning('TCER for testcase %s and testplan %s is existing. ID: %s'%
                        (_tc_id, _tc_testplan_id, _tc_tcer_id))
   else:
      Logger.log_error("Create TCER failed. Please check whether test case with id '%s' is existing on RQM or not. Reason: %s"%(_tc_id, res['message']))
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
      Logger.log("Create result for test '%s' successfully!"%_tc_name)
      _tc_result_id = res['id']
   else:
      Logger.log_error("Create result for test '%s' failed. Reason"%(_tc_name, res['message']))
      return
   if _tc_result_id not in RQMClient.lTCResultIDs:
      RQMClient.lTCResultIDs.append(_tc_result_id)

   # Append lTestcaseIDs (for linking testplan/testsuite)
   if _tc_id not in RQMClient.lTestcaseIDs:
      RQMClient.lTestcaseIDs.append(_tc_id)

def RobotResults2RQM(args=None):
   """
   Import robot results from output.xml to RQM - IBM Rational Quality Manager.

   Flow to import Robot results to RQM: 
      1. Process provided arguments from command line
      2. Login Rational Quality Management (RQM)
      3. Parse Robot results
      4. Import results into RQM 
      5. Link all executed testcases to provided testplan/testsuite ID

   Args:
      args : Argument parser object:
         - `outputfile` : path to the output file or directory with output files to be imported.
         - `host` : RQM host url.
         - `project` : RQM project name.
         - `user` : user for RQM login.
         - `password` : user password for RQM login.
         - `testplan` : RQM testplan ID.
         - `recursive` : if True, then the path is searched recursively for log files to be imported.
         - `createmissing` : if True, then all testcases without fcid are created when importing.
         - `updatetestcase` : if True, then testcases information on RQM will be updated bases on robot testfile.
         - `dryrun` : if True, then just check the RQM authentication and show what would be done.

   Returns:
      None.
   """

   # 1. process provided arguments from command line as default
   args = __process_commandline()
   Logger.config(dryrun=args.dryrun)
   
   # 2. Login Rational Quality Management (RQM)
   RQMClient = CRQMClient(args.user, args.password, args.project, args.host)
   try:
      bSuccess = RQMClient.login()
      if bSuccess:
         Logger.log("Login RQM as user '%s' successfully!"%args.user)
      else:
         Logger.log_error("Could not login to RQM: 'Unkown reason'")
   except Exception as reason:
      Logger.log_error("Could not login to RQM: '%s'" % str(reason))

   # 3. Parse Robot results
   sLogFileType="NONE"
   if os.path.exists(args.outputfile):
      sLogFileType="PATH"
      if os.path.isfile(args.outputfile):
         sLogFileType="FILE"  
   else:
      Logger.log_error("logfile not existing: '%s'" % str(args.outputfile), fatal_error=True)

   listEntries=[]
   if sLogFileType=="FILE":
      listEntries.append(args.outputfile)
   else:
      if args.recursive:
         Logger.log("Searching log files recursively...")
         for root, dirs, files in os.walk(args.outputfile):
            for file in files:
               if file.endswith(".xml"):
                  listEntries.append(os.path.join(root, file))
                  Logger.log(os.path.join(root, file), indent=2)
      else:
         Logger.log("Searching log files...")
         for file in os.listdir(args.outputfile):
            if file.endswith(".xml"):
               listEntries.append(os.path.join(args.outputfile, file))
               Logger.log(os.path.join(args.outputfile, file), indent=2)

      # Terminate tool with error when no logfile under provided outputfile folder
      if len(listEntries) == 0:
         Logger.log_error("No logfile under '%s' folder." % str(args.outputfile), fatal_error=True)

   sources = tuple(listEntries)
   result = ExecutionResult(*sources)
   result.configure()
   
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
      suite_info = process_suite(RQMClient, result.suite)

      # Link all imported testcase ID(s) with testplan
      Logger.log("Linking all imported testcase ID(s) with testplan ...")
      RQMClient.linkListTestcase2Testplan(args.testplan)

      # Update testcase(s) with generated ID(s)
      # Under developing

   except Exception as reason:
      Logger.log_error("Could not import results to RQM. Reason: %s"%reason, fatal_error=True)

   # 5. Disconnect from RQM
   RQMClient.disconnect()
   Logger.log("Import all results successfully!")
