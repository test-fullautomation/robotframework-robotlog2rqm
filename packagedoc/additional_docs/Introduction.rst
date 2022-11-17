.. Copyright 2020-2022 Robert Bosch GmbH

.. Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

.. http://www.apache.org/licenses/LICENSE-2.0

.. Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

`###PACKAGENAME### <###URL###>`_ tool provides the ability to interact with RQM resources (test 
plan, test case, build, ...).

`###PACKAGENAME### <###URL###>`_ tool uses RqmAPI_ to:
   - get resource: by given ID or all vailable entities of resource type.
   - update resource: by given ID.
   - create new resource: with resource templates under RQM_templates_ folder

.. _RqmAPI: https://jazz.net/wiki/bin/view/Main/RqmApi
.. _RQM_templates: https://github.com/test-fullautomation/robotframework-robotlog2rqm/tree/develop/RobotLog2RQM/RQM_templates