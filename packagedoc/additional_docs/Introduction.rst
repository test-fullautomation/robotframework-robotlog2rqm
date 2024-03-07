.. Copyright 2020-2024 Robert Bosch GmbH

.. Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

.. http://www.apache.org/licenses/LICENSE-2.0

.. Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

**RobotLog2RQM** facilitates the import of  Robot Framework result file(s) in 
***.xml** format into IBM® Rational® Quality Manager (RQM) resources.

It introduces the **CRQM Class**, offering the capability to interact with 
various RQM resources, including test plans, test cases, builds, and more, 
through the RqmAPI_ to:

* retrieve RQM resources: obtain resources by a given ID or retrieve all available entities of a specified resource type.
* update RQM resources: modify existing resources by providing the relevant ID.
* create new RQM resources: generate new resources using predefined templates located in the RQM_templates_ folder.

So that **RobotLog2RQM** tool can:

* create all required resources (*Test Case Excution Record*, *Test Case
  Execution Result*, ...) for new test cases on RQM.
* link all test cases to provided test plan.
* add new test results for existing test cases on RQM.
* update existing test cases on RQM.

.. _RqmAPI: https://jazz.net/wiki/bin/view/Main/RqmApi
.. _RQM_templates: https://github.com/test-fullautomation/robotframework-robotlog2rqm/tree/develop/RobotLog2RQM/RQM_templates
