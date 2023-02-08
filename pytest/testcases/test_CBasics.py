#  Copyright 2020-2022 Robert Bosch GmbH
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
# --------------------------------------------------------------------------------------------------------------
#
# test_CBasics.py
#
# XC-CT/ECA3-Queckenstedt
#
# 03.02.2023
#
# --------------------------------------------------------------------------------------------------------------

# -- import standard Python modules
import os, sys, shlex, subprocess, pytest

from PythonExtensionsCollection.String.CString import CString

# --------------------------------------------------------------------------------------------------------------

class Test_CBasics:
   """Basic tests"""

   # --------------------------------------------------------------------------------------------------------------
   #TM***
   @pytest.mark.parametrize(
      "Description", ["Command line test",]
   )
   def test_cmd_line_1_get_version(self, Description):
      """pytest 'CBasics'"""

      sThisScriptPath = os.path.dirname(CString.NormalizePath(__file__))
      sPython = CString.NormalizePath(sys.executable)
      sApp    = CString.NormalizePath("../../RobotLog2RQM/robotlog2rqm.py", sReferencePathAbs=sThisScriptPath)
      listCmdLineParts = []
      listCmdLineParts.append(f"\"{sPython}\"")
      listCmdLineParts.append(f"\"{sApp}\"")
      listCmdLineParts.append("-v")
      sCmdLine = " ".join(listCmdLineParts)
      print(f"(debug) sCmdLine: {sCmdLine}")
      listCmdLineParts = shlex.split(sCmdLine)
      nReturn = subprocess.call(listCmdLineParts)
      assert nReturn == 0

   # eof def test_cmd_line_1_get_version(self, Description):

# eof class Test_CBasics

# --------------------------------------------------------------------------------------------------------------
