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
# File: CRQM.py
#
# Initialy created by Tran Duy Ngoan(RBVH/ECM11) / January 2021
#
# This is CRQMClient class which is used to interact with RQM via RQM REST APIs
#  
# History:
# 
# 2020-01-08:
#  - initial version
#
# ******************************************************************************

import requests
import os
import sys
from io import BytesIO
from lxml import etree
import time
import urllib.parse

# Disable request warning
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

#
#  helper functions for processing xml data
#
######################################################################## 

def get_xml_tree(file_name, bdtd_validation=True):
   '''
   Parse xml object from file.

   Args:
      file_name : path to file or file-like object.
      bdtd_validation : if True, validate against a DTD referenced by the document.

   Returns:
      oTree : xml etree object
   '''
   oTree = None
   try:
      oParser = etree.XMLParser(dtd_validation=bdtd_validation)
      oTree = etree.parse(file_name, oParser)
   except Exception as reason:
      print("Could not parse xml data. Reason: %s"%reason)
      exit(1)
   return oTree

#
#  IBM Rational Quality Manager
#
########################################################################### 
class CRQMClient():
   '''
   CRQMClient class uses RQM REST APIs to get, create and update resources
   (testplan, testcase, test result, ...) on RQM - Rational Quality Manager
   
   Resoure type mapping:
      - buildrecord:          Build Record
      - configuration:        Test Environment
      - testplan:             Test Plan
      - testsuite:            Test Suite
      - suiteexecutionrecord: Test Suite Execution Record (TSER)
      - testsuitelog:         Test Suite Log
      - testcase:             Test Case
      - executionworkitem:    Test Execution Record (TCER)
      - executionresult:      Execution Result

   '''
   RESULT_STATES = ['paused', 'inprogress', 'notrun', 'passed', 'incomplete', 
                    'inconclusive', 'part_blocked', 'failed', 'error', 
                    'blocked', 'perm_failed', 'deferred']

   def __init__(self, user, password, project, host):
      """
      Constructor for CRQMClient class

      Args:
         user : user name for RQM's authentication.

         password : user password for RQM's authentication.

         project : RQM project name.

         host : the url that RQM is hosted.

      Returns:
         CRQMClient instance

      """
      # RQM authentication 
      self.host    = host
      self.userID  = user
      self.pw      = password
      self.projectname = project
      self.projectID = urllib.parse.quote_plus(project) # encode URI for project name
      self.session = requests.Session()

      # Required request headers for creating new resource
      self.headers = {
                        'Accept'             : 'application/xml',
                        'Content-Type'       : 'application/rdf+xml',
                        'X-Jazz-CSRF-Prevent': '',
                        'OSLC-Core-Version'  : '2.0'
                     }

      # Templates location which is uesd for importing
      self.templatesDir = os.path.join(os.path.dirname(__file__),'RQM_templates')

      # Data for mapping and linking
      self.dMappingTCID  = dict()
      self.lTestcaseIDs  = list()
      self.dBuildVersion = dict()
      self.dConfiguation = dict()
      self.dTeamAreas    = dict()
      self.lTCERIDs      = list()
      self.lTCResultIDs  = list()
      self.lStartTimes   = list()
      self.lEndTimes     = list()

      # RQM configuration info
      self.testplan      = None
      self.build         = None
      self.configuration = None
      self.createmissing = None
      self.testsuite     = None

   def login(self):
      '''
      Log in RQM by provided user & password.

      Note: 
         When the authentication is successful, the JSESSIONID from cookies will 
         be stored as header for later POST method.

      Returns:
         True if successful, False otherwise.
      '''
      bSuccess = False
      res = self.session.post(self.host + '/qm/j_security_check', allow_redirects=True, verify=False, 
                              data={'j_username':self.userID,'j_password':self.pw})
      if res.status_code == 200:
         # verify login
         if self.verifyProjectName():
            # get JSESSIONID from cookies and store into request headers
            try:
               self.headers['X-Jazz-CSRF-Prevent'] = self.session.cookies['JSESSIONID']
               bSuccess = True
            except Exception as error:
               raise Exception('Could not get JSESSIONID from cookies!')
      return bSuccess

   def verifyProjectName(self):
      ''' 
      Verify the project name by searching it in `project-areas` XML response.

      Note:
         The found project ID will be stored and:
            - required for `team-areas` request (project name cannot be used)
            - used for all later request urls instead of project name

      Returns:
         - True if the authentication is successful.
         - False if the authentication is failed.
      '''
      bSuccess = False

      # Try to get project UUID from provided project name
      # Then use project UUID instead of name in request URL
      resProjects = self.session.get(self.host + '/qm/process/project-areas', 
                                       allow_redirects=True, verify=False)
      if resProjects.status_code == 200:
         oProjects=get_xml_tree(BytesIO(str(resProjects.text).encode()),
                                 bdtd_validation=False)
         nsmap = oProjects.getroot().nsmap
         for oProject in oProjects.findall('jp06:project-area', nsmap):
            if oProject.attrib['{%s}name'%nsmap['jp06']] == self.projectname:
               sProjectURL = oProject.find("jp06:url", nsmap).text
               # replace encoded uri project name by project UUID
               self.projectID = sProjectURL.split("/")[-1]
               bSuccess = True
               break
      if not bSuccess:
         raise Exception(f"Could not find project with name '{self.projectname}'")

      return bSuccess   

   def disconnect(self):
      """
      Disconnect from RQM 
      """
      self.session.close()

   def config(self, plan_id, build_name=None, config_name=None, 
              createmissing=False, suite_id=None):
      '''
      Configure RQMClient with testplan ID, build, configuration, createmissing, ...
         - Verify the existence of provided testplan ID.
         - Verify the existences of provided build and configuration names
           before creating new ones.

      Args:
         plan_id : testplan ID of RQM project for importing result(s).

         build_name (optional) : the `Build Record` for linking result(s).
            Set it to `None` if not be used, the empty name '' may lead to error.

         config_name (optional) : the `Test Environment` for linking result(s).
            Set it to `None` if not be used, the empty name '' may lead to error.

         createmissing (optional) : in case this argument is set to `True`, 
            the testcase without `tcid` information will be created on RQM.

         suite_id (optional) : testsuite ID of RQM project for importing result(s).
      
      Returns:
         None.
      '''
      try:
         self.createmissing = createmissing
         self.testsuite = suite_id
         self.testplan  = plan_id
         # Verify testplan ID
         res_plan = self.getResourceByID('testplan', plan_id)
         if res_plan.status_code != 200:
            raise Exception('Testplan with ID %s is not existing!'%str(plan_id))

         # Verify and create build version if required
         if build_name != None:
            if build_name == '':
               raise Exception("Build name should not be empty.")
            self.getAllBuildRecords()
            res_build = self.createBuildRecord(build_name)
            if res_build['success'] or res_build['status_code'] == "303":
               self.build = res_build['id']
            else:
               raise Exception("Cannot create build '%s': %s"%
                               (build_name, res_build['message']))

         # Verify and create test environment if required
         if config_name != None:
            if config_name == '':
               raise Exception("Configuration name should not be empty.")
            self.getAllConfigurations()
            res_conf = self.createConfiguration(config_name)
            if res_conf['success'] or res_conf['status_code'] == "303":
               self.configuration = res_conf['id']
            else:
               raise Exception("Cannot create configuration '%s': %s"%
                               (config_name, res_conf['message']))

         # get all team-areas for testcase template
         self.getAllTeamAreas()

      except Exception as error:
         raise Exception('Configure RQMClient failed: %s'%error)

   def userURL(self, userID):
      '''
      Return interaction URL of provided userID

      Args:
         userID : the user ID
      
      Returns:
         userURL : the interaction URL of provided userID
      '''
      userURL = self.host + "/jts/resource/itemName/com.ibm.team.repository.Contributor/" + userID
      return userURL

   def integrationURL(self, resourceType, id=None, forceinternalID=False):
      '''
      Return interaction URL of provided reource and ID.

      Note:
         ID can be internalID (contains only digits) or externalID.

      Args:
         resourceType : the RQM resource type (e.g: "testplan", "testcase", ...)

         id (optional) : ID of given resource.
            If given: the specified url to resource ID is returned.
            If `None`: the url to resource type (to get all entity) is returned.

         forceinternalID (optional) : force to return the url of resource as internal ID.

      Returns:
         integrationURL : interaction URL of provided reource and ID.
      '''
      integrationURL = self.host + "/qm/service/com.ibm.rqm.integration.service.IIntegrationService/resources/" + \
                       self.projectID + '/' + resourceType 
      if(id != None):
         ### externalID
         if (not str(id).isdigit()) and (not forceinternalID):
            integrationURL += '/'+ str(id)  
         else:
            ### internalID
            integrationURL += "/urn:com.ibm.rqm:" + resourceType + ':' + str(id)  
      return integrationURL

   def webIDfromResponse(self, response, tagID='rqm:resultId'):
      '''
      Get internal ID (number) from response of POST method.

      Note:
         Only `executionresult` has response text. Other resources has only response header.

      Args:
         response : the response from POST method.

         tagID : tag name which contains ID information.

      Returns:
         resultId : internal ID (as number).
      '''
      resultId = ''
      try:
         oResponse = get_xml_tree(BytesIO(str(response).encode()),
                                          bdtd_validation=False)
         oResultId = oResponse.find(tagID, oResponse.getroot().nsmap)
         resultId = oResultId.text
      except Exception as error:
         raise Exception("Cannot get ID from response. Reason: %s"%str(error))
      return resultId

   def webIDfromGeneratedID(self, resourrceType, generateID):
      '''
      Return web ID (ns2:webId) from generate ID by get resource data from RQM.

      Note:
         - This method is only used for generated `testcase`, `executionworkitem` and `executionresult`.
         - `buildrecord` and `configuration` does not have `ns2:webId` in response data.

      Args:
         resourrceType : the RQM resource type.

         generateID : the Slug ID which is returned in `Content-Location` from POST response.

      Returns:
         webID : web ID (number).
      '''
      webID = generateID
      # below resources that have ns2:webId node in response data
      lSupportedResources = [ 'attachment', 
                              'executionresult', 
                              'executionscript', 
                              'executionworkitem', 
                              'keyword', 
                              'remotescript', 
                              'suiteexecutionrecord', 
                              'testcase', 
                              'testplan', 
                              'testscript', 
                              'testsuite', 
                              'testsuitelog']
      if resourrceType in lSupportedResources:
         resResource = self.getResourceByID(resourrceType, generateID)
         if resResource.status_code == 200:
            oResource = get_xml_tree(BytesIO(str(resResource.text).encode()),
                                     bdtd_validation=False)
            oWebID = oResource.find('ns2:webId', oResource.getroot().nsmap)
            if oWebID != None:
               webID = oWebID.text
         else:
            raise Exception("Cannot get web ID of generated testcase!")
      return webID

   #
   #  Methods to get resources
   #
   ###########################################################################
   def getResourceByID(self, resourceType, id):
      '''
      Return data of provided resource and ID by GET method

      Args:
         resourrceType : the RQM resource type.

         id : ID of resource.

      Returns:
         res : response data of GET request.
      '''
      res = self.session.get(self.integrationURL(resourceType, id), 
                             allow_redirects=True, verify=False)
      return res

   def getAllByResource(self, resourceType):
      '''
      Return all entries of provided resource by GET method.

      Note:
         This method will try to fetch all entries in all pages of resource.

      Args:
         resourrceType : the RQM resource type.

      Returns:
         dReturn : a dictionary which contains response status, message and data.
      '''
      dReturn = {
         'success' : False, 
         'message' : '',
         'data'    : {}
      }

      try:
         resData = self.getResourceByID(resourceType, None)
         oResData = get_xml_tree(BytesIO(str(resData.text).encode()),
                                 bdtd_validation=False)
         nsmap = oResData.getroot().nsmap

         for oEntry in oResData.findall('entry', nsmap):
            sURLID = oEntry.find("./id", nsmap).text
            sEntryID = (sURLID.split("/")[-1]).split(":")[-1]
            sEntryName = oEntry.find("./title", nsmap).text
            dReturn['data'][sEntryID] = sEntryName
         
         # Try to get data from next page
         oNextPage = oResData.find('./link[@rel="next"]', nsmap)
         if oNextPage != None:
            sNextPageURL = oNextPage.attrib['href']
            sResourceWithPageIdx = (sNextPageURL.split("/")[-1])
            res = self.getAllByResource(sResourceWithPageIdx)
            if res['success']:
               dReturn['data'].update(res['data'])
            else:
               raise Exception("Get data of %s failed. Reason: %s"%
                               (resourceType, res['message']))
         dReturn['success'] = True
      except Exception as error:
         dReturn['message'] = str(error)
      return dReturn

   def getAllBuildRecords(self):
      '''
      Get all available build records of project on RQM and store them into 
      `dBuildVersion` property.   
      '''
      res = self.getAllByResource('buildrecord')
      if res['success']:
         self.dBuildVersion = res['data']
      else:
         raise Exception("Get all builds failed. Reason: %s"%res['message'])

   def getAllConfigurations(self):
      '''
      Get all available configurations of project on RQM and store them into 
      `dConfiguation` property.
      '''
      res = self.getAllByResource('configuration')
      if res['success']:
         self.dConfiguation = res['data']
      else:
         raise Exception("Get all configurations failed. Reason: %s"%res['message'])

   def getAllTeamAreas(self):
      '''
      Get all available team-areas of project on RQM and store them into 
      `dTeamAreas` property.

      Example: 
         {\
            'teamA' : '{host}/qm/process/project-areas/{project-id}/team-areas/{teamA-id},\
            'teamB' : '{host}/qm/process/project-areas/{project-id}/team-areas/{teamB-id}\
         }
      '''
      req_url = f"{self.host}/qm/process/project-areas/{self.projectID}/team-areas"
      resTeamAreas = self.session.get(req_url, allow_redirects=True, verify=False)
      if resTeamAreas.status_code == 200:
         oTeams=get_xml_tree(BytesIO(str(resTeamAreas.text).encode()),
                             bdtd_validation=False)
         nsmap = oTeams.getroot().nsmap
         for oTeam in oTeams.findall('jp06:team-area', nsmap):
            sTeamName = oTeam.attrib["{%s}name"%nsmap['jp06']]
            sTeamURL  = oTeam.find("jp06:url", nsmap).text
            self.dTeamAreas[sTeamName] = sTeamURL
      else:
         raise Exception(f"Could not get 'team-areas' of project '{self.projectname}'.")
   

   #
   #  Methods to create XML template for resources
   #
   ###########################################################################
   def addTeamAreaNode(self, root, sTeam):
      '''
      Append `team-area` node which contains URL to given team-area into xml template

      Note: 
         `team-area` information is case-casesensitive

      Args:
         root : xml root object.

         sTeam : team name to be added.

      Returns:
         root : xml root object with addition `team-area` node.
      '''
      if sTeam in self.dTeamAreas:
         oTeamArea = etree.Element('{http://jazz.net/xmlns/prod/jazz/process/0.6/}team-area', root.nsmap)
         oTeamURL  = etree.Element('{http://jazz.net/xmlns/prod/jazz/process/0.6/}url', root.nsmap)
         oTeamURL.text = self.dTeamAreas[sTeam]
         oTeamArea.append(oTeamURL)
         root.append(oTeamArea)
      else:
         raise Exception(f"Could not find team-area with name '{sTeam}'")

      return root

   def createTestcaseTemplate(self, testcaseName, sDescription='', 
                              sComponent='', sFID='', sTeam='', sRobotFile='', 
                              sTestType='', sASIL='', sOwnerID=''):
      '''
      Return testcase template from provided information.

      Args:
         testcaseName : testcase name.

         sDescription (optional) : testcase description.

         sComponent (optional) : component which testcase is belong to.

         sFID (optional) : function ID(requirement ID) for linking.

         sTeam (optional) : team name for linking.

         sRobotFile (optional) : link to robot file on source control.

         sTestType (optional) : test type information.

         sASIL (optional) : ASIL information.

         sOwnerID (optional) : user ID of testcase owner.

      Returns:
         xml template as string.
      '''
      sTemplatePath = os.path.join(self.templatesDir ,'testcase.xml')
      oTree         = get_xml_tree(sTemplatePath, bdtd_validation=False)
      root         = oTree.getroot()
      nsmap        = root.nsmap
      # prepare required data for template
      testcaseTittle  = testcaseName

      # find nodes to change data 
      oTittle      = oTree.find('ns3:title', nsmap)
      oDescription = oTree.find('ns3:description', nsmap)
      oOwner       = oTree.find('ns5:owner', nsmap)
      
      # change nodes's data
      oTittle.text       = testcaseTittle
      oDescription.text  = sDescription

      # Incase not specify owner in template or input data, set it as provided user in cli
      if sOwnerID:
         oOwner.text = sOwnerID
         oOwner.attrib['{%s}resource' % nsmap['ns7']] = self.userURL(sOwnerID)
      elif oOwner.text == None or oOwner.text == '':
         oOwner.text = self.userID
         oOwner.attrib['{%s}resource' % nsmap['ns7']] = self.userURL(self.userID)

      # Modify Categories data
      # These Categories and default values are defined in template testcase.xml
      # If the category is not required for project, remove/comment it from the template
      oComponent = oTree.find('ns2:category[@term="Component"]', nsmap)
      if (oComponent != None) and sComponent:
         oComponent.set('value', sComponent)

      # Component is used in CMD project but Categories is used in others
      oCategory = oTree.find('ns2:category[@term="Categories"]', nsmap)
      if (oCategory != None) and sComponent:
         oCategory.set('value', sComponent)

      oTesttype = oTree.find('ns2:category[@term="Test Type"]', nsmap)
      if (oTesttype != None) and sTestType:
         oTesttype.set('value', sTestType)

      oASIL = oTree.find('ns2:category[@term="ASIL relevant"]', nsmap)
      if (oASIL != None) and sASIL:
         oASIL.set('value', sASIL) 

      # Modify custom attributes
      oRequirementID = oTree.find('ns2:customAttributes/ns2:customAttribute/[ns2:name="Requirement ID"]', nsmap)
      if oRequirementID != None:
         oRequirementID.find('ns2:value', nsmap).text = sFID

      oRobotFile = oTree.find('ns2:customAttributes/ns2:customAttribute/[ns2:name="Robot file"]', nsmap)
      if oRobotFile != None:
         oRobotFile.find('ns2:value', nsmap).text = sRobotFile

      # link to provided valid team-area
      if sTeam:
         root = self.addTeamAreaNode(root, sTeam)

      # return xml template as string
      return etree.tostring(oTree)

   def createTCERTemplate(self, testcaseID, testcaseName, testplanID,
                          confID='', sTeam='', sOwnerID=''):
      '''
      Return testcase execution record template from provided information

      Args:
         testcaseID : testcase ID.

         testcaseName : testcase name.

         testplanID : testplan ID for linking.

         confID (optional) : configuration - `Test Environment` for linking.

         sTeam (optional) : team name for linking.

         sOwnerID (optional) : user ID of testcase owner.

      Returns:
         xml template as string.
      '''
      sTemplatePath = os.path.join(self.templatesDir, 'executionworkitem.xml')
      oTree         = get_xml_tree(sTemplatePath, bdtd_validation=False)
      root = oTree.getroot()
      nsmap = root.nsmap
      # prepare required data for template
      TCERTittle  = 'TCER: '+testcaseName

      # Check tcid is internalid or externalid
      testcaseURL = self.integrationURL('testcase', testcaseID)
      testplanURL = self.integrationURL('testplan', testplanID)
      testerURL   = self.userURL(self.userID)

      # find nodes to change data 
      oTittle   = oTree.find('ns3:title', nsmap)
      oTestcase = oTree.find('ns2:testcase', nsmap)
      oTestplan = oTree.find('ns2:testplan', nsmap)
      oOwner    = oTree.find('ns5:owner', nsmap)

      # change nodes's data
      oTittle.text             = TCERTittle
      oTestcase.attrib['href'] = testcaseURL
      oTestplan.attrib['href'] = testplanURL
      # Incase not specify owner in template or input data, set it as provided user in cli
      if sOwnerID:
         oOwner.text = sOwnerID
         oOwner.attrib['{%s}resource' % nsmap['ns7']] = self.userURL(sOwnerID)
      elif oOwner.text == None or oOwner.text == '':
         oOwner.text = self.userID
         oOwner.attrib['{%s}resource' % nsmap['ns7']] = testerURL

      if confID:
         oConf   = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/}configuration', nsmap=nsmap)
         confURL = self.integrationURL('configuration', confID)
         oConf.set('href', confURL)
         root.append(oConf)

      # link to provided valid team-area
      if sTeam:
         root = self.addTeamAreaNode(root, sTeam)

      # return xml template as string
      return etree.tostring(oTree)

   def createExecutionResultTemplate(self, testcaseID, testcaseName, testplanID, 
         TCERID, resultState, startTime='', endTime='', duration='',  testPC='', 
         testBy='', lastlog='', buildrecordID='', sTeam='', sOwnerID=''):
      '''
      Return testcase execution result template from provided information

      Args:
         testcaseID : testcase ID.

         testcaseName : testcase name.

         testplanID : testplan ID for linking.

         TCERID : testcase execution record (TCER) ID for linking.

         resultState : testcase result status.

         startTime : testcase start time.

         endTime (optional) : testcase end time.

         duration (optional) : testcase duration.

         testPC (optional) : test PC which executed testcase.

         testBy (optional) : user ID who executed testcase.

         lastlog (optional) : traceback information (for Failed testcase).

         buildrecordID (optional) : `Build Record` ID for linking.

         sTeam (optional) : team name for linking.

         sOwnerID (optional) : user ID of testcase owner.

      Returns:
         xml template as string.
      '''
      sTemplatePath = os.path.join(self.templatesDir, 'executionresult.xml')
      oTree         = get_xml_tree(sTemplatePath, bdtd_validation=False)
      root = oTree.getroot()
      nsmap = root.nsmap
      # prepare required data for template
      prefixState  = 'com.ibm.rqm.execution.common.state.'
      resultTittle = 'Execution result: '+testcaseName
      testcaseURL  = self.integrationURL('testcase', testcaseID)
      testplanURL  = self.integrationURL('testplan', testplanID)
      TCERURL      = self.integrationURL('executionworkitem', TCERID)
      testerURL    = self.userURL(self.userID)

      # find nodes to change data 
      oTittle      = oTree.find('ns3:title', nsmap)
      oMachine     = oTree.find('ns16:machine', nsmap)
      oState       = oTree.find('ns5:state', nsmap)
      oTestcase    = oTree.find('ns2:testcase', nsmap)
      oTestplan    = oTree.find('ns2:testplan', nsmap)
      oTCER        = oTree.find('ns2:executionworkitem', nsmap)
      oOwner       = oTree.find('ns5:owner', nsmap)
      oTester      = oTree.find('ns16:testedby/ns16:tester', nsmap)
      oStarttime   = oTree.find('ns16:starttime', nsmap)
      oEndtime     = oTree.find('ns16:endtime', nsmap)
      oTotalRunTime= oTree.find('ns16:totalRunTime', nsmap)
      oDetails     = oTree.find('{http://jazz.net/xmlns/alm/qm/v0.1/executionresult/v0.1}details/{http://www.w3.org/1999/xhtml}div')

      # change nodes's data
      oTittle.text             = resultTittle
      oMachine.text            = testPC
      # set default RQM state as inconclusive
      oState.text              = prefixState + 'inconclusive'
      if resultState.lower() in self.RESULT_STATES:
         oState.text = prefixState +resultState.lower()
      oTestcase.attrib['href'] = testcaseURL
      oTestplan.attrib['href'] = testplanURL
      oTCER.attrib['href']     = TCERURL
      # Incase not specify owner in template or input data, set it as provided user in cli
      if sOwnerID:
         oOwner.text = sOwnerID
         oOwner.attrib['{%s}resource' % nsmap['ns7']] = self.userURL(sOwnerID)
      elif oOwner.text == None or oOwner.text == '':
         oOwner.text = self.userID
         oOwner.attrib['{%s}resource' % nsmap['ns7']] = testerURL 
      # currently assign user name is not worked
      # oTester.text             = testBy 
      oTester.text             = self.userID
      oTester.attrib['{%s}resource' % nsmap['ns7']] = testerURL
      oStarttime.text          = str(startTime).replace(' ', 'T')
      oEndtime.text            = str(endTime).replace(' ', 'T')
      oTotalRunTime.text       = str(duration)
      if lastlog != None and lastlog.strip() != '':
         lines = lastlog.strip().splitlines()
         oPre      = etree.Element('pre')
         oCode      = etree.Element('code')
         for line in lines:
            oLine      = etree.Element('div')
            # oLine.set('dir', "ltr")
            oLine.text = line
            oCode.append(oLine)
         oPre.append(oCode)
         oDetails.append(oPre)
      # oDetails.text            = lastlog
      if buildrecordID:
         oBuildRecord = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/}buildrecord', nsmap=nsmap)
         buildrecordURL = self.integrationURL('buildrecord', buildrecordID)
         oBuildRecord.set('href', buildrecordURL)
         root.append(oBuildRecord)

      # link to provided valid team-area
      if sTeam:
         root = self.addTeamAreaNode(root, sTeam)

      # return xml template as string
      return etree.tostring(oTree)

   def createBuildRecordTemplate(self, buildName):
      '''
      Return build record template from provided build name

      Args:
         buildName : `Build Record` name.

      Returns:
         xml template as string.
      '''
      sTemplatePath = os.path.join(self.templatesDir, 'buildrecord.xml')
      oTree         = get_xml_tree(sTemplatePath, bdtd_validation=False)

      nsmap        = oTree.getroot().nsmap
      oTittle      = oTree.find('ns3:title', nsmap)
      oTittle.text = buildName

      return etree.tostring(oTree)

   def createConfigurationTemplate(self, confName):
      '''
      Return configuration - Test Environment template from provided configuration name

      Args:
         buildName : configuration - `Test Environment` name.

      Returns:
         xml template as string.
      '''      
      sTemplatePath = os.path.join(self.templatesDir, 'configuration.xml')
      oTree         = get_xml_tree(sTemplatePath, bdtd_validation=False)

      nsmap        = oTree.getroot().nsmap
      oTittle      = oTree.find('ns3:title', nsmap)
      oTittle.text = confName

      return etree.tostring(oTree)

   def createTSERTemplate(self, testsuiteID, testsuiteName, testplanID, 
                          confID='', sOwnerID=''):
      '''
      Return testsuite execution record (TSER) template from provided 
      configuration name

      Args:
         testsuiteID : testsuite ID.

         testsuiteName : testsuite name.

         testplanID : testplan ID for linking.

         confID (optional) : configuration - `Test Environment` ID for linking.

         sOwnerID (optional) : user ID of testsuite owner.

      Returns:
         xml template as string.
      '''  
      sTemplatePath = os.path.join(self.templatesDir, 
                                   'suiteexecutionrecord.xml')
      oTree         = get_xml_tree(sTemplatePath, bdtd_validation=False)
      root = oTree.getroot()
      # prepare required data for template
      TSERTittle   = 'TSER: ' + testsuiteName
      testsuiteURL = self.integrationURL('testsuite', testsuiteID)
      testplanURL  = self.integrationURL('testplan', testplanID)
      testerURL    = self.userURL(self.userID)

      # find nodes to change data 
      nsmap      = oTree.getroot().nsmap
      oTittle    = oTree.find('ns4:title', nsmap)
      oTestsuite = oTree.find('ns2:testsuite', nsmap)
      oTestplan  = oTree.find('ns2:testplan', nsmap)
      oOwner     = oTree.find('ns6:owner', nsmap)

      # change nodes's data
      oTittle.text              = TSERTittle
      oTestsuite.attrib['href'] = testsuiteURL
      oTestplan.attrib['href']  = testplanURL
      # Incase not specify owner in template or input data, 
      # set its value as provided user in cli
      if sOwnerID:
         oOwner.text = sOwnerID
         oOwner.attrib['{%s}resource' % nsmap['ns1']] = self.userURL(sOwnerID)
      elif oOwner.text == None or oOwner.text == '':
         oOwner.text = self.userID
         oOwner.attrib['{%s}resource' % nsmap['ns1']] = testerURL
      if confID:
         # TSER: configuration node with empty href attribute will cause Internal Server Error (500)
         oConf   = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/}configuration', nsmap=nsmap)
         confURL = self.integrationURL('configuration', confID)
         oConf.set('href', confURL)
         root.append(oConf)

      # return xml template as string
      return etree.tostring(oTree)

   def createTestsuiteResultTemplate(self, testsuiteID, testsuiteName, TSERID, 
                                     lTCER, lTCResults, startTime='', 
                                     endTime='', duration='', sOwnerID=''):
      '''
      Return testsuite execution result template from provided 
      configuration name

      Args:
         testsuiteID : testsuite ID.

         testsuiteName : testsuite name.

         TSERID : testsuite execution record (TSER) ID for linking.

         lTCER : list of testcase execution records (TCER) for linking.

         lTCResults : list of testcase results for linking.

         startTime (optional) : testsuite start time.

         endTime (optional) : testsuite end time.

         duration (optional) : testsuite duration.

         sOwnerID (optional) : user ID of testsuite owner.

      Returns:
         xml template as string.

      '''  
      sTemplatePath = os.path.join(self.templatesDir, 'testsuitelog.xml')
      oTree         = get_xml_tree(sTemplatePath, bdtd_validation=False)

      # prepare required data for template
      resultTittle  = 'Testsuite result: ' + testsuiteName
      testsuiteURL  = self.integrationURL('testsuite', testsuiteID)
      TSERURL       = self.integrationURL('suiteexecutionrecord', TSERID)
      testerURL    = self.userURL(self.userID)
      if startTime == '':
         startTime = min(self.lStartTimes)
      if endTime == '':
         endTime = max(self.lEndTimes)
      if duration == '':
         duration = (time.mktime(endTime.timetuple()) - time.mktime(startTime.timetuple()))*1000

      # find nodes to change data 
      root         = oTree.getroot()
      nsmap        = root.nsmap
      oTittle      = oTree.find('ns4:title', nsmap)
      oTestsuite   = oTree.find('ns2:testsuite', nsmap)
      oTSER        = oTree.find('ns2:suiteexecutionrecord', nsmap)
      oOwner       = oTree.find('ns6:owner', nsmap)
      oStarttime   = oTree.find('ns18:starttime', nsmap)
      oEndtime     = oTree.find('ns18:endtime', nsmap)
      oTotalRunTime= oTree.find('ns18:totalRunTime', nsmap)
      # oBuildRecord = oTree.find('ns2:buildrecord', nsmap)
      oSuiteElems  = oTree.find('ns18:suiteelements', nsmap)
      oState       = oTree.find('ns6:state', nsmap)

      # change nodes's data
      oState.text = 'com.ibm.rqm.execution.common.state.inconclusive'
      oTittle.text = resultTittle
      oTestsuite.attrib['href'] = testsuiteURL
      oTSER.attrib['href']      = TSERURL
      # Incase not specify owner in template or input data, 
      # set its value as provided user in cli
      if sOwnerID:
         oOwner.text = sOwnerID
         oOwner.attrib['{%s}resource' % nsmap['ns1']] = self.userURL(sOwnerID)
      elif oOwner.text == None or oOwner.text == '':
         oOwner.text = self.userID
         oOwner.attrib['{%s}resource' % nsmap['ns1']] = testerURL
      oStarttime.text          = str(startTime).replace(' ', 'T')
      oEndtime.text            = str(endTime).replace(' ', 'T')
      oTotalRunTime.text       = str(duration)
      for idx, sTCER in enumerate(lTCER):
         sTCERURL = self.integrationURL('executionworkitem', sTCER)
         oSuiteElem = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/tsl/v0.1/}suiteelement', nsmap=nsmap)
         oIndex     = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/tsl/v0.1/}index', nsmap=nsmap)
         oTCER      = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/tsl/v0.1/}executionworkitem', nsmap=nsmap)
         oIndex.text = str(idx)
         oTCER.set('href', sTCERURL)
         oSuiteElem.append(oIndex)
         oSuiteElem.append(oTCER)
         oSuiteElems.append(oSuiteElem)

         # Link all test case execution results to testsuite result
         oExecutionResult = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/}executionresult', nsmap=nsmap)
         sTCResultURL = self.integrationURL('executionresult', lTCResults[idx])
         oExecutionResult.set('href', sTCResultURL)
         root.append(oExecutionResult)
         
      # return xml template as string
      return etree.tostring(oTree)

   #
   #  Methods to create RQM resources
   #
   ###########################################################################
   def createResource(self, resourceType, content):
      '''
      Create new resource with provided data from template by POST method.

      Args:
         resourceType : resource type.

         content: xml template as string.

      Returns:
         returnObj: a response dictionary which contains status, ID, status_code and error message.
            {\
               'success' : False, \
               'id': None, \
               'message': '', \
               'status_code': ''\
            }
      '''
      returnObj = {
         'success' : False, 
         'id': None, 
         'message': '', 
         'status_code': ''
      }
      if(self.headers['X-Jazz-CSRF-Prevent'] == ''):
         returnObj['message'] = "JSESSIONID is missing for RQM resource's creation"
         return returnObj

      res = self.session.post(self.integrationURL(resourceType), 
                              allow_redirects=True, verify=False, 
                              data=content, headers=self.headers)
      returnObj['status_code'] = res.status_code
      # Check whether successful response
      if res.status_code != 201:
         returnObj['message'] = res.reason
         if res.status_code == 303:
            ### remove itergrationURL in case status_code=303
            sRemove = self.integrationURL(resourceType, '', forceinternalID=True)
            returnObj['id'] = res.headers['Content-Location'].replace(sRemove, '')

         # On IBM Engineering Test Management Version: 7.0.2
         # When trying to create new TCER but it is existing for testcase and testplan, 
         # the response is 200 instead of 303 as previous RQM version 6.x.x
         # Below step is trying to get existing TCER ID from response <200>
         elif res.status_code == 200 and res.text:
            try:
               returnObj['id'] = self.webIDfromResponse(res.text, tagID='ns2:webId')
            except Exception as error:
               returnObj['message'] = "Extract ID information from response failed. Reason: %s" % str(error)
      else:
         ### Get new creation ID from response
         try: 
            # try to get the web ID (internalID) from response of POST method
            if res.text and (res.text != ''):
               returnObj['id'] = self.webIDfromResponse(res.text)
            # The externalID of new resource is responsed in 'Content-Location' 
            # from response headers
            elif res.headers['Content-Location'] != '':
               returnObj['id'] = res.headers['Content-Location']
               returnObj['id'] = self.webIDfromGeneratedID(resourceType, returnObj['id'])
            returnObj['success'] = True

         except Exception as error:
            returnObj['message'] = "Extract ID information from response failed. Reason: %s" % str(error)

      return returnObj

   def createBuildRecord(self, sBuildSWVersion, forceCreate=False):
      '''
      Create new build record.

      Note:
         Tool will check if build record is already existing or not (both on RQM and current execution).

      Args:
         sBuildSWVersion : build version - `Build Record` name.

         forceCreate (optional) : if True, force to create new build record without existing verification.

      Returns:
         returnObj: a response dictionary which contains status, ID, status_code and error message.
            {\
               'success' : False, \
               'id': None, \
               'message': '', \ 
               'status_code': '' \
            }.
      '''
      # check existing build record in this execution
      returnObj = {'success' : False, 'id': None, 'message': '', 'status_code': ''}
      if (sBuildSWVersion not in self.dBuildVersion.values()) or forceCreate:
         sBuildTemplate = self.createBuildRecordTemplate(sBuildSWVersion)
         returnObj  = self.createResource('buildrecord', sBuildTemplate) 
         if returnObj['success']:
            # store existing build ID for next verification   
            self.dBuildVersion[returnObj['id']] = sBuildSWVersion
      else:
         idx = list(self.dBuildVersion.values()).index(sBuildSWVersion)
         returnObj['id'] = list(self.dBuildVersion.keys())[idx]
         returnObj['status_code'] = "303"
         returnObj['message'] = "Build record '%s' is already existing."%sBuildSWVersion
      return returnObj

   def createConfiguration(self, sConfigurationName, forceCreate=False):
      '''
      Create new configuration - test environment.

      Note:
         Tool will check if configuration is already existing or not (both on RQM and current execution).

      Args:
         sConfigurationName : configuration - `Test Environment` name.

         forceCreate (optional) : if True, force to create new Test Environment without existing verification.

      Returns:
         returnObj: a response dictionary which contains status, ID, status_code and error message.      
            {\
               'success' : False, \
               'id': None, \
               'message': '', \
               'status_code': ''\
            }
      '''
      returnObj = {'success' : False, 'id': None, 'message': '', 'status_code': ''}
      # check existing build record in this executioon
      sConfID = ''
      if (sConfigurationName not in self.dConfiguation.values()) or forceCreate:
         sConfTemplate = self.createConfigurationTemplate(sConfigurationName)
         returnObj  = self.createResource('configuration', sConfTemplate)
         if returnObj['success']:
            # store existing configuration ID for next verification   
            self.dConfiguation[returnObj['id']] = sConfigurationName
      else:
         idx = list(self.dConfiguation.values()).index(sConfigurationName)
         returnObj['id'] = list(self.dConfiguation.keys())[idx]
         returnObj['status_code'] = "303"
         returnObj['message'] = "Test environment '%s' is already existing."%sConfigurationName
      return returnObj

   #
   #  Methods to update RQM resources
   #
   ###########################################################################
   def updateResourceByID(self, resourceType, id, content):
      '''
      Update data of provided resource and ID by PUT method.

      Args:
         resourceType : resource type.

         id : resource id.

         content : xml template as string.
         
      Returns:
         res : response object from PUT request.
      '''
      res = self.session.put(self.integrationURL(resourceType, id), allow_redirects=True, verify=False, data=content)
      return res

   def linkListTestcase2Testplan(self, testplanID, lTestcases=None):
      '''
      Link list of test cases to provided testplan ID.

      Args:
         testplanID : testplan ID to link given testcase(s).

         lTestcases : list of testcase(s) to be linked with given testplan.
            If None (as default), `lTestcaseIDs` property will be used as list of testcase.
         
      Returns:
         res : response object which contains status and error message.
            {\
               'success' : False, \
               'message': ''\
            }
      '''
      returnObj = {'success' : False, 'message': ''}
      if lTestcases == None:
         lTestcases = self.lTestcaseIDs
      if len(lTestcases): 
         resTestplanData = self.getResourceByID('testplan', testplanID)
         oTree = get_xml_tree(BytesIO(str(resTestplanData.text).encode()),bdtd_validation=False)
         # RQM XML response using namespace for nodes
         # use namespace mapping from root for access response XML
         root = oTree.getroot()
         
         for sTCID in lTestcases:
            sTestcaseURL = self.integrationURL('testcase', sTCID)
            oTC = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/}testcase', nsmap=root.nsmap)
            oTC.set('href', sTestcaseURL)
            root.append(oTC)

         # Update test plan data with linked testcases and PUT to RQM
         resUpdateTestplan = self.updateResourceByID('testplan', testplanID, etree.tostring(oTree))
         if resUpdateTestplan.status_code == 200:
            returnObj['success'] = True
         else:
            returnObj['message'] = str(resUpdateTestplan.reason)
      else:
         returnObj['message'] = "No testcase for linking."
      return returnObj      

   def linkListTestcase2Testsuite(self, testsuiteID, lTestcases=None):
      '''
      Link list of test cases to provided testsuite ID

      Args:
         testsuiteID : testsuite ID to link given testcase(s).

         lTestcases : list of testcase(s) to be linked with given testsuite.
            If None (as default), `lTestcaseIDs` property will be used as list of testcase.
         
      Returns:
         res : response object which contains status and error message.
            {\
               'success' : False, \
               'message': ''\
            }
      '''
      returnObj = {'success' : False, 'message': ''}
      if lTestcases == None:
         lTestcases = self.lTestcaseIDs
      if len(lTestcases): 
         resTestsuiteData = self.getResourceByID('testsuite', testsuiteID)
         oTree=get_xml_tree(BytesIO(str(resTestsuiteData.text).encode()),bdtd_validation=False)
         # RQM XML response using namespace for nodes
         # use namespace mapping from root for access response XML
         root = oTree.getroot()

         oSuiteElems  = oTree.find('ns2:suiteelements', root.nsmap)
         for sTCID in lTestcases:
            sTestcaseURL = self.integrationURL('testcase', sTCID)
            oTC = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/}testcase', nsmap=root.nsmap)
            oTC.set('href', sTestcaseURL)
            oElem = etree.Element('{http://jazz.net/xmlns/alm/qm/v0.1/}suiteelement', nsmap=root.nsmap)
            oElem.append(oTC)
            oSuiteElems.append(oElem)
         root.append(oSuiteElems)

         # Update test suite data with linked testcases and PUT to RQM
         resUpdateTestsuite = self.updateResourceByID('testsuite', testsuiteID, etree.tostring(oTree))
         if resUpdateTestsuite.status_code == 200:
            returnObj['success'] = True
         else:
            returnObj['message'] = str(resUpdateTestsuite.reason)
      else:
         returnObj['message'] = "No testcase for linking."
      return returnObj