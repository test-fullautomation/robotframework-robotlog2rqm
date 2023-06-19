.. Copyright 2020-2023 Robert Bosch GmbH

.. Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

.. http://www.apache.org/licenses/LICENSE-2.0

.. Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

**RobotLog2RQM** helps to import the Robot result file(s) as ***.xml** format
into IBM® Rational® Quality Manager - RQM resources.

It provides ability (**CRQM Class**) to interact with RQM resources such as test plan, test case,
build, ... via RqmAPI_ to:

* Get RQM resource: by given ID or all vailable entities of resource type.
* Update RQM resource: by given ID.
* Create new RQM resource: with resource templates under RQM_templates_ folder.

So that **RobotLog2RQM** tool can:

* Create all required resources (*Test Case Excution Record*, *Test Case
  Execution Result*, ...) for new testcase on RQM.
* Link all testcases to provided testplan.
* Add new test result for existing testcase on RQM.
* Update existing testcase on RQM.

.. _RqmAPI: https://jazz.net/wiki/bin/view/Main/RqmApi
.. _RQM_templates: https://github.com/test-fullautomation/robotframework-robotlog2rqm/tree/develop/RobotLog2RQM/RQM_templates
