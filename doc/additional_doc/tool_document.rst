.. Copyright 2020-2022 Robert Bosch GmbH

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

RobotResults2RQM tool's Documentation
=====================================

Introduction:
-------------
RobotResults2RQM_ tool provides the ability to interact with RQM resources (test 
plan, test case, build, ...).

RobotResults2RQM_ tool uses RqmAPI_ to:
   - get resource: by given ID or all vailable entities of resource type.
   - update resource: by given ID.
   - create new resource: with resource templates under RQM_templates_ folder


Sample RobotFramework Testcase:
-------------------------------
For test case management, we need some tracable information such as version, 
testcase ID, component, ... to manage and track testcase(s) on RQM.

So, this information can be provided in **Metadata** (for the whole 
testsuite/execution info: version, build, ...) and **[Tags]** information 
(for specific testcase info: component, testcase ID, requirement ID, ...).

Sample Robot testcase with the neccessary information for importing to RQM:
::

   *** Settings ***
   Metadata   project      ROBFW             # Test Environment
   Metadata   version_sw   SW_VERSION_0.1    # Build Record
   Metadata   component    Import_Tools      # Component - is used for test case
   Metadata   machine      %{COMPUTERNAME}   # Hostname
   Metadata   team-area    Internet Team RQM  # team-area (case-sensitive)

   *** Test Cases ***
   Testcase 01
      [Documentation]   This test is traceable with provided tcid  
      [Tags]   TCID-1001   FID-112   FID-111
      Log      This is Testcase 01

   Testcase 02
      [Documentation]  This new testcase will be created if -createmissing argument 
                  ...  is provided when importing
      [Tags]   FID-113  
      Log      This is Testcase 02

Tool features:
--------------
By default, tool will base on provided arguments (see [Usage](#usage)) 
and *tcid* information in Robot test case(s) to:

- Login the RQM server and verify the provided ``project``, ``testplan``.
- Create build record and test environment (if already provided in Robot test case and not existing on RQM) for execution.
- Create new Test Case Execution Record - TCER (if it is not existing) bases on test case ID and ``testplan`` ID.
- Create new Test Case Execution Result which contents the detail and result state of test case.
- Link all test case(s) to provided ``testplan``.

Besides, RobotResults2RQM_ tool also supports to create new test case(s) 
which is not existing on RQM (do not have *tcid* information) 
while importing result(s) to RQM with optional argument ``-createmissing``.

Robot Testcase information on RQM:
----------------------------------------------------------------------
For more detail how the RobotFramework testcase information is displayed 
on RQM, please refer be mapping table:

.. table::
   :widths: 12 16 35 37

   +---------------------------------------------------------+-----------------------------------------------------------------------------------------------------------------------+
   | **RQM data**                                            | **RobotFramework**                                                                                                    |
   +----------------------------+----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   | **Resource**               | **Attribute/Field**        | **Testsuite/Testcase**                                                | **Output.xml**                                |
   +----------------------------+----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   | Build Record               | Title                      | **Metadata**   version_sw   *${Build}*                                | ``//suite/metadata/item[@name="version_sw"]`` |
   +----------------------------+----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   | Test Environment           | Title                      | **Metadata**   project   *${Environment}*                             | ``//suite/metadata/item[@name="project"]``    |
   +----------------------------+----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   | Test Case                  | ID                         | **[Tags]**   tcid-*xxx*                                               | ``//suite/test/tags/tag[@text="tcid-*xxx*"]`` |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Name                       | test name                                                             | ``//suite/test/@name``                        |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Team Area                  | **Metadata**   team-area   *${Team_Area}*                             | ``//suite/metadata/item[@name="team-area"]``  |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Description                | test doc - [Documentation]                                            | ``//suite/test/doc/@text``                    |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Owner                      | provided ``user`` in cli                                              |                                               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Component/Categories       | **Metadata**   component   *${Component}*                             | ``//suite/metadata/item[@name="component"]``  |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Requirement ID             | **[Tags]**   fid-*yyy*                                                | ``//suite/test/tags/tag[@text="fid-*yyy*"]``  |
   +----------------------------+----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   | Test Case Execution Record | Owner                      | provided ``user`` in cli                                              |                                               |
   | (TCER)                     +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Team Area                  | **Metadata**   team-area   *${Team_Area}*                             | ``//suite/metadata/item[@name="team-area"]``  |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Test Plan                  | Interaction URL to provided ``testplan`` in cli                       |                                               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Test Case                  | Interaction URL to provided testcase ID:                              | ``//suite/test/tags/tag[@text="tcid-*xxx*"]`` |
   |                            |                            | - Testcase ID which provided in [Tags]: tcid-*xxx*                    |                                               |
   |                            |                            | - Generated testcase ID if argument ``-createmissing`` is used in cli |                                               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Test Environment           | **Metadata**   project   *${Environment}*                             | ``//suite/metadata/item[@name="project"]``    |
   +----------------------------+----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   | Test Result                | Owner                      | provided ``user`` in cli                                              |                                               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Tested By                  | provided ``user`` in cli - userid must be used                        |                                               |
   |                            |                            | (value as username Metadata: tester does not work now)                |                                               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Team Area                  | **Metadata**   team-area   *${Team_Area}*                             | ``//suite/metadata/item[@name="team-area"]``  |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Actual Result              | Test case result (PASSED, FAILED, UNKNOWN)                            | ``//suite/test/status/@status``               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Host Name                  | **Metadata**   machine   *%{COMPUTERNAME}*                            | ``//suite/metadata/item[@name="machine"]``    |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Test Plan                  | Interaction URL to provided ``testplan`` in cli                       |                                               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Test Case                  | Interaction URL to provided testcase ID:                              | ``//suite/test/tags/tag[@text="tcid-*xxx*"]`` |
   |                            |                            | - Testcase ID which provided in **[Tags]**: tcid-*xxx*                |                                               |
   |                            |                            | - Generated testcase ID if ``-createmissing`` is used                 |                                               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Test Case Execution Record | Interaction URL to TCER ID                                            |                                               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Build                      | **Metadata**   version_sw   *${Build}*                                | ``//suite/metadata/item[@name="version_sw"]`` |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Start Time                 | Test case start time                                                  | ``//suite/test/status/@starttime``            |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | End Time                   | Test case end time                                                    | ``//suite/test/status/@endtime``              |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Total Run Time             | Calculated from start and end time                                    |                                               |
   |                            +----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+
   |                            | Result Details             | Test case message log                                                 | ``//suite/test/status/@text``                 |
   +----------------------------+----------------------------+-----------------------------------------------------------------------+-----------------------------------------------+

.. _RqmAPI: https://jazz.net/wiki/bin/view/Main/RqmApi
.. _RQM_templates: https://github.com/test-fullautomation/robotframework-testresult2rqmtool/tree/develop/RobotResults2RQM/RQM_templates
.. _RobotResults2RQM: https://github.com/test-fullautomation/robotframework-testresult2rqmtool