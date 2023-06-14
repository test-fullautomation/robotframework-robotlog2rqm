# RobotLog2RQM Description

The Python package **RobotLog2RQM** provides ability to import [Robot
Framework test
result](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#output-file)
as **\*.xml** format file(s) to [IBM® Rational® Quality
Manager](https://www.ibm.com/support/knowledgecenter/SSYMRC_6.0.2/com.ibm.rational.test.qm.doc/topics/c_qm_overview.html)
(RQM) for test management.

**RobotLog2RQM** tool helps to:

-   Create all required resources (*Test Case Excution Record*, *Test
    Case Execution Result*, \...) for new testcase on RQM.
-   Link all testcases to provided testplan.
-   Add new test result for existing testcase on RQM.
-   Update existing testcase on RQM.

**RobotLog2RQM** tool is operating system independent and only works
with Python 3.

## How to install

**RobotLog2RQM** can be installed in two different ways.

1.  Installation via PyPi (recommended for users)

    ``` 
    pip install RobotLog2RQM
    ```

    [RobotLog2RQM in
    PyPi](https://pypi.org/project/robotframework-robotlog2rqm/)

2.  Installation via GitHub (recommended for developers)

    -   Clone the **robotframework-robotlog2rqm** repository to your
        machine.

        ``` 
        git clone https://github.com/test-fullautomation/robotframework-robotlog2rqm.git
        ```

        [RobotLog2RQM in
        GitHub](https://github.com/test-fullautomation/robotframework-robotlog2rqm)

    -   Install dependencies

        **RobotLog2RQM** requires some additional Python libraries.
        Before you install the cloned repository sources you have to
        install the dependencies manually. The names of all related
        packages you can find in the file `requirements.txt` in the
        repository root folder. Use pip to install them:

        ``` 
        pip install -r ./requirements.txt
        ```

        Additionally install **LaTeX** (recommended: TeX Live). This is
        used to render the documentation.

    -   Configure dependencies

        The installation of **RobotLog2RQM** includes to generate the
        documentation in PDF format. This is done by an application
        called **GenPackageDoc**, that is part of the installation
        dependencies (see `requirements.txt`).

        **GenPackageDoc** uses **LaTeX** to generate the documentation
        in PDF format. Therefore **GenPackageDoc** needs to know where
        to find **LaTeX**. This is defined in the **GenPackageDoc**
        configuration file

        ``` 
        packagedoc\packagedoc_config.json
        ```

        Before you start the installation you have to introduce the
        following environment variable, that is used in
        `packagedoc_config.json`:

        -   `GENDOC_LATEXPATH` : path to `pdflatex` executable

    -   Use the following command to install **RobotLog2RQM**:

        ``` 
        python setup.py install
        ```

After succesful installation, the executable file **RobotLog2RQM** will
be available (under *Scripts* folder of Python on Windows and
*\~/.local/bin/* folder on Linux).

In case above location is added to **PATH** environment variable then
you can run it directly as operation system\'s command.

## How to use

**RobotLog2RQM** tool requires the Robot Framework `output.xml` result
file(s) which will be imported, RQM information(e.g. host url, project,
\...) and user credential(user name and password) to interact with RQM
resources.

Use below command to get tools\'s usage:

    RobotLog2RQM -h

The usage should be showed as below:

    usage: RobotLog2RQM (RobotXMLResult to RQM importer) [-h] [-v] [--recursive] 
                        [--createmissing] [--updatetestcase] [--dryrun] 
                        resultxmlfile host project user password testplan

    RobotLog2RQM imports XML result files (default: output.xml) generated by the 
    Robot Framework into an IBM Rational Quality Manager.

    positional arguments:
    resultxmlfile     absolute or relative path to the xml result file 
                      or directory of result files to be imported.
    host              RQM host url.
    project           project on RQM.
    user              user for RQM login.
    password          password for RQM login.
    testplan          testplan ID for this execution.

    optional arguments:
    -h, --help        show this help message and exit
    -v, --version     Version of the RobotLog2RQM importer.
    --recursive       if set, then the path is searched recursively for 
                      log files to be imported.
    --createmissing   if set, then all testcases without tcid are created 
                      when importing.
    --updatetestcase  if set, then testcase information on RQM will be updated 
                      bases on robot testfile.
    --dryrun          if set, then verify all input arguments 
                      (includes RQM authentication) and show what would be done.

The below command is simple usage witth all required arguments to import
Robot Framework results into RQM:

    RobotLog2RQM <outputfile> <host> <project> <user> <password> <testplan>

Besides the executable file, you can also run tool as a Python module

    python -m RobotLog2RQM <outputfile> <host> <project> <user> <password> <testplan>

### Example

In order the import the Robot result(s) to RQM, we need the `output.xml`
result file.

So, firstly execute the Robot testcase(s) to get the `output.xml` result
file.

Sample Robot testcase which contains neccessary information for
importing into RQM:

    *** Settings ***
    Metadata   project      ROBFW             # Test Environment
    Metadata   version_sw   SW_VERSION_0.1    # Build Record
    Metadata   component    Import_Tools      # Component - is used for test case
    Metadata   machine      %{COMPUTERNAME}   # Hostname
    Metadata   team-area    Internet Team RQM  # team-area (case-sensitive)

    *** Test Cases ***
    Testcase 01
       [Documentation]   This test is traceable with provided tcid  
       [Tags]   TCID-1001   FID-112   FID-111    robotfile-https://github.com/test-fullautomation
       Log      This is Testcase 01

    Testcase 02
       [Documentation]  This new testcase will be created if --createmissing argument 
                   ...  is provided when importing
       [Tags]   FID-113  robotfile-https://github.com/test-fullautomation
       Log      This is Testcase 02

After getting `output.xml` result file, use below command to import that
result file into testplan ID `720` of `ROBFW-AIO` project which is
hosted at `https://sample-rqm-host.com`

    RobotLog2RQM output.xml https://sample-rqm-host.com ROBFW-AIO test_user test_pw 720

Then, open RQM with your favourite browser and you will see that the
test case execution records and their results are imported in the given
testplan ID.

### Sourcecode Documentation

To understand more detail about the tool\'s features and how Robot test
cases and their results are reflected on RQM, please refer to
[RobotLog2RQM tool's
Documentation](https://github.com/test-fullautomation/robotframework-robotlog2rqm/blob/develop/RobotLog2RQM/RobotLog2RQM.pdf).

## Feedback

To give us a feedback, you can send an email to [Thomas
Pollerspöck](mailto:Thomas.Pollerspoeck@de.bosch.com).

In case you want to report a bug or request any interesting feature,
please don\'t hesitate to raise a ticket.

## Maintainers

[Thomas Pollerspöck](mailto:Thomas.Pollerspoeck@de.bosch.com)

[Tran Duy Ngoan](mailto:Ngoan.TranDuy@vn.bosch.com)

## Contributors

[Nguyen Huynh Tri Cuong](mailto:Cuong.NguyenHuynhTri@vn.bosch.com)

[Mai Dinh Nam Son](mailto:Son.MaiDinhNam@vn.bosch.com)

[Tran Hoang Nguyen](mailto:Nguyen.TranHoang@vn.bosch.com)

[Holger Queckenstedt](mailto:Holger.Queckenstedt@de.bosch.com)

## License

Copyright 2020-2022 Robert Bosch GmbH

Licensed under the Apache License, Version 2.0 (the \"License\"); you
may not use this file except in compliance with the License. You may
obtain a copy of the License at

> [![License: Apache
> v2](https://img.shields.io/pypi/l/robotframework.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an \"AS IS\" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
