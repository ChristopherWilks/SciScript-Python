import json
import time

import sys
from io import StringIO

import requests
import pandas

from SciServer import Authentication, Config


def getSchemaName():
    """
    Returns the WebServiceID that identifies the schema for a user in MyScratch database with CasJobs.

    :return: WebServiceID of the user (string).
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: wsid = CasJobs.getSchemaName()

    .. seealso:: CasJobs.getTables.
    """
    token = Authentication.getToken()
    if token is not None and token != "":

        keystoneUserId = Authentication.getKeystoneUserWithToken(token).id
        usersUrl = Config.CasJobsRESTUri + "/users/" + keystoneUserId
        headers={'X-Auth-Token': token,'Content-Type': 'application/json'}
        getResponse = requests.get(usersUrl,headers=headers)
        if getResponse.status_code != 200:
            raise Exception("Error when getting schema name. Http Response from CasJobs API returned status code " + str(getResponse.status_code) + ":\n" + getResponse.content.decode());

        jsonResponse = json.loads(getResponse.content.decode())
        return "wsid_" + str(jsonResponse["WebServicesId"])
    else:
        raise Exception("User token is not defined. First log into SciServer.")


def getTables(context="MyDB"):
    """
    Gets the names, size and creation date of all tables in a database context that the user has access to.

    :param context:	database context (string)
    :return: The result is a json object with format [{"Date":seconds,"Name":"TableName","Rows":int,"Size",int},..]
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: tables = CasJobs.getTables("MyDB")

    .. seealso:: CasJobs.getSchemaName
    """

    token = Authentication.getToken()
    if token is not None and token != "":

        TablesUrl = Config.CasJobsRESTUri + "/contexts/" + context + "/Tables"

        headers={'X-Auth-Token': token,'Content-Type': 'application/json'}

        getResponse = requests.get(TablesUrl,headers=headers)

        if getResponse.status_code != 200:
            raise Exception("Error when getting table description from database context " + str(context) + ".\nHttp Response from CasJobs API returned status code " + str(getResponse.status_code) + ":\n" + getResponse.content.decode());

        jsonResponse = json.loads(getResponse.content.decode())

        return jsonResponse
    else:
        raise Exception("User token is not defined. First log into SciServer.")


def executeQuery(sql, context="MyDB", format="readable"):
    """
    Executes a synchronous SQL query in a CasJobs database context.

    :param sql: sql query (string)
    :param context: database context (string)
    :param format: parameter (string) that specifies the return type:\n
    \t\t'pandas': pandas.DataFrame.\n
    \t\t'csv': a csv string.\n
    \t\t'readable' : a StringIO, readable object (has the .read() method) wrapping a csv string that can be passed into pandas.read_csv for example.\n
    \t\t'fits' : a StringIO, readable object wrapping the result in fits format.\n
    \t\t'json': a dictionary created from a JSON string with the Query, a Result consisting of a Columns and a Data field.\n
    :return: The result is a json object with format [{"Date":seconds,"Name":"TableName","Rows":int,"Size",int},..]
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error. Throws an exception if parameter 'format' is not correctly specified.
    :example: table = CasJobs.executeQuery(sql="select 1 as foo, 2 as bar",context="MyDB")

    .. seealso:: CasJobs.submitJob, CasJobs.getTables, SkyServer.sqlSearch
    """

    if (format == "pandas") or (format =="json"):
        acceptHeader="application/json+array"
    elif (format == "csv") or (format == "readable"):
        acceptHeader = "text/plain"
    elif format == "fits":
        acceptHeader = "application/fits"
    else:
        raise Exception("Error when executing query. Illegal format parameter specification: " + str(format));

    QueryUrl = Config.CasJobsRESTUri + "/contexts/" + context + "/query"

    TaskName = "";
    if Config.isSciServerComputeEnvironment():
        TaskName = "Compute.SciScript-Python.CasJobs.executeQuery"
    else:
        TaskName = "SciScript-Python.CasJobs.executeQuery"

    query = {"Query": sql, "TaskName": TaskName}

    data = json.dumps(query).encode()

    headers = {'Content-Type': 'application/json', 'Accept': acceptHeader}
    token = Authentication.getToken()
    if token is not None and token != "":
        headers['X-Auth-Token'] = token

    postResponse = requests.post(QueryUrl,data=data,headers=headers)
    if postResponse.status_code != 200:
        raise Exception("Error when executing query. Http Response from CasJobs API returned status code " + str(postResponse.status_code) + ":\n" + postResponse.content.decode());

    r=postResponse.content.decode()
    if (format == "readable"):
        return StringIO(r)
    elif format == "pandas":
        r=json.loads(r)
        return pandas.DataFrame(r['Result'][0]['Data'],columns=r['Result'][0]['Columns'])
    elif format == "csv":
        return r
    elif format == "json":
        return json.loads(r)
    elif format == "fits":
        return StringIO(r)
    else: # should not occur
        raise Exception("Error when executing query. Illegal format parameter specification: " + str(format));

def submitJob(sql, context="MyDB"):
    """
    Submits an asynchronous SQL query to the CasJobs queue.

    :param sql: sql query (string)
    :param context:	database context (string)
    :return: Returns the CasJobs jobID (integer).
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: jobid = CasJobs.submitJob("select 1 as foo","MyDB")

    .. seealso:: CasJobs.executeQuery, CasJobs.getJobStatus, CasJobs.waitForJob.
    """
    token = Authentication.getToken()
    if token is not None and token != "":

        QueryUrl = Config.CasJobsRESTUri + "/contexts/" + context + "/jobs"

        TaskName = "";
        if Config.isSciServerComputeEnvironment():
            TaskName = "Compute.SciScript-Python.CasJobs.submitJob"
        else:
            TaskName = "SciScript-Python.CasJobs.submitJob"

        query = {"Query": sql, "TaskName": TaskName}

        data = json.dumps(query).encode()

        headers = {'Content-Type': 'application/json', 'Accept': "text/plain"}
        headers['X-Auth-Token']=  token


        putResponse = requests.put(QueryUrl,data=data,headers=headers)
        if putResponse.status_code != 200:
            raise Exception("Error when submitting a job. Http Response from CasJobs API returned status code " + str(putResponse.status_code) + ":\n" + putResponse.content.decode());

        return int(putResponse.content.decode())
    else:
        raise Exception("User token is not defined. First log into SciServer.")


def getJobStatus(jobid):
    """
    Shows the status of a job submitted to CasJobs.

    :param jobid: id of job (integer)
    :return: Returns a dictionary object containing the job status and related metadata. If jobid is the empty string, then returns a list with the statuses of all previous jobs.
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: CasJobs.waitForJob(CasJobs.submitJob("select 1"))

    .. seealso:: status <- CasJobs.getJobStatus(CasJobs.submitJob("select 1"))
    """
    token = Authentication.getToken()
    if token is not None and token != "":

        QueryUrl = Config.CasJobsRESTUri + "/jobs/" + str(jobid)

        headers={'X-Auth-Token': token,'Content-Type': 'application/json'}

        postResponse =requests.get(QueryUrl,headers=headers)
        if postResponse.status_code != 200:
            raise Exception("Error when getting the status of job " + str(jobid) + ".\nHttp Response from CasJobs API returned status code " + str(postResponse.status_code) + ":\n" + postResponse.content.decode());

        return json.loads(postResponse.content.decode())
    else:
        raise Exception("User token is not defined. First log into SciServer.")


def waitForJob(jobid, verbose=True):
    """
    Queries the job status from casjobs every 2 seconds and waits for the casjobs job to return a status of 3, 4, or 5.

    :param jobid: id of job (integer)
    :param verbose: if True, will print "wait" messages on the screen while the job is not done. If False, will suppress printing messages on the screen.
    :return: Returns a dictionary object containing the job status and related metadata
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: CasJobs.waitForJob(CasJobs.submitJob("select 1"))

    .. seealso:: CasJobs.submitJob, CasJobs.getJobStatus.
    """

    try:
        complete = False

        waitingStr = "Waiting..."
        back = "\b" * len(waitingStr)
        if verbose:
            print(waitingStr)

        while not complete:
            if verbose:
                print(back)
                print(waitingStr)
            jobDesc = getJobStatus(jobid)
            jobStatus = int(jobDesc["Status"])
            if jobStatus in (3, 4, 5):
                complete = True
                if verbose:
                    print(back)
                    print("Done!")
            else:
                time.sleep(2)

        return jobDesc
    except Exception as e:
        raise e;


def getFitsFileFromQuery(fileName, queryString, context="MyDB"):
    """
    Executes a CasJobs quick query and writes the result to a fits (http://www.stsci.edu/institute/software_hardware/pyfits) file.

    :param fileName: path to the local fits file to be created (string)
    :param queryString: sql query (string)
    :param context: database context (string)
    :return: Returns True if the fits file was created successfully.
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: CasJobs.getFitsFileFromQuery("/home/user/myFile.fits","select 1 as foo")

    .. seealso:: CasJobs.submitJob, CasJobs.getJobStatus, CasJobs.executeQuery, CasJobs.getPandasDataFrameFromQuery, CasJobs.getNumpyArrayFromQuery
    """
    try:
        fitsResponse = executeQuery(queryString, context=context, format="fits")

        theFile = open(fileName, "w+b")
        theFile.write(fitsResponse.read())
        theFile.close()

        return True

    except Exception as e:
        raise e

# no explicit index column by default
def getPandasDataFrameFromQuery(queryString, context="MyDB", index_col=None):
    """
    Executes a casjobs quick query and returns the result as a pandas dataframe object with an index (http://pandas.pydata.org/pandas-docs/stable/).

    :param queryString: sql query (string)
    :param context: database context (string)
    :param index_col: index of the column (integer) that contains the table index. Default set to None.
    :return: Returns a Pandas dataframe containing the results table.
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: df = CasJobs.getPandasDataFrameFromQuery("select 1 as foo", context="MyDB", index_col=0)

    .. seealso:: CasJobs.submitJob, CasJobs.getJobStatus, CasJobs.executeQuery, CasJobs.getFitsFileFromQuery, CasJobs.getNumpyArrayFromQuery
    """
    try:
        cvsResponse = executeQuery(queryString, context=context,format="readable")

        #if the index column is not specified then it will add it's own column which causes problems when uploading the transformed data
        dataFrame = pandas.read_csv(cvsResponse, index_col=index_col)

        return dataFrame

    except Exception as e:
        raise e

def getNumpyArrayFromQuery(queryString, context="MyDB"):
    """
    Executes a casjobs query and returns the results table as a Numpy array (http://docs.scipy.org/doc/numpy/).

    :param queryString: sql query (string)
    :param context: database context (string)
    :return: Returns a Numpy array storing the results table.
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: array = CasJobs.getNumpyArrayFromQuery("select 1 as foo", context="MyDB")

    .. seealso:: CasJobs.submitJob, CasJobs.getJobStatus, CasJobs.executeQuery, CasJobs.getFitsFileFromQuery, CasJobs.getPandasDataFrameFromQuery

    """
    try:

        dataFrame = getPandasDataFrameFromQuery(queryString, context)
        return dataFrame.as_matrix()

    except Exception as e:
        raise e


#require pandas for now but be able to take a string in the future
def uploadPandasDataFrameToTable(dataFrame, tableName, context="MyDB"):
    """
    Uploads a pandas dataframe object into a CasJobs table.

    :param dataFrame: Pandas data frame containg the data (pandas.core.frame.DataFrame)
    :param tableName: name of CasJobs table to be created.
    :param context: database context (string)
    :return: Returns True if the dataframe was uploaded successfully.
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: response = CasJobs.uploadPandasDataFrameToTable(CasJobs.getPandasDataFrameFromQuery("select 1 as foo", context="MyDB", index_col=0), "NewTableFromDataFrame")

    .. seealso:: CasJobs.uploadCSVDataToTable
    """
    try:
        if dataFrame.index.name == "" or dataFrame.index.name is None:
            dataFrame.index.name = "index"

        sio = dataFrame.to_csv().encode("utf8")

        return uploadCSVDataToTable(sio, tableName, context)

    except Exception as e:
        raise e

def uploadCSVDataToTable(CVSdata, tableName, context="MyDB"):
    """
    Uploads CSV data into a CasJobs table.

    :param CVSdata: a CSV table in string format.
    :param tableName: name of CasJobs table to be created.
    :param context: database context (string)
    :return: Returns True if the csv data was uploaded successfully.
    :raises: Throws an exception if the user is not logged into SciServer (use Authentication.login for that purpose). Throws an exception if the HTTP request to the CasJobs API returns an error.
    :example: csv = CasJobs.getPandasDataFrameFromQuery("select 1 as foo", context="MyDB", index_col=0).to_csv().encode("utf8"); response = CasJobs.uploadCSVDataToTable(csv, "NewTableFromDataFrame")

    .. seealso:: CasJobs.uploadPandasDataFrameToTable
    """
    token = Authentication.getToken()
    if token is not None and token != "":

        #if (Config.executeMode == "debug"):
        #    print "Uploading ", sys.getsizeof(CVSdata), "bytes..."
        tablesUrl = Config.CasJobsRESTUri + "/contexts/" + context + "/Tables/" + tableName

        headers={}
        headers['X-Auth-Token']= token

        postResponse = requests.post(tablesUrl,data=CVSdata,headers=headers)
        if postResponse.status_code != 200:
            raise Exception("Error when uploading CSV data into CasJobs table " + tableName + ".\nHttp Response from CasJobs API returned status code " + str(postResponse.status_code) + ":\n" + postResponse.content.decode());

        return True

    else:
        raise Exception("User token is not defined. First log into SciServer.")
