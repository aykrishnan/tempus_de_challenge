"""Tempus challenge  - Operations and Functions.

Describes the code definition of the Airflow Operator for the tasks in the DAG.
The 'Tempus Bonus Challenge' dag performs similar tasks to those of the
'Tempus Challenge' dag. Hence, to encourage function reusability, all the
functions executed by both dag pipelines are implemented in the same Operations
class.
"""

# import env
import errno
import json
import logging
import os
import time

from airflow.models import Variable

import requests


log = logging.getLogger(__name__)

# store the current directory of the airflow home folder
# airflow creates a home environment variable pointing to the location
HOME_DIRECTORY = str(os.environ['HOME'])


class MissingApiKey(ValueError):
    pass


class FileStorage:
    """Handles functionality for data storage."""

    @classmethod
    def create_storage(cls, **context):
        """Create tempoary data storage for the current DAG pipeline.

        # Arguments
            :param context: current Airflow context in which the function or
                operator is being run in.
            :type context: dict
        """

        log.info("Running create_storage method")

        # stores the dag_id which will be the name of the created folder
        dag_id = str(context['dag'].dag_id)

        # Python's os.environ property is used, in its place, during unit
        # tests for setting environment variables. However, the variables
        # don't seem to carry over between Airflow tasks. (Using either
        # Airflow's Variable or XCom classes might be more ideal here.)
        os.environ["current_dag_id"] = dag_id

        # Push the dag_id to the downstream SimpleHTTPOperator task
        # Using Airflow's global Variables:
        Variable.set("current_dag_id", dag_id)

        # list of the directories that will be created to store data
        data_directories = ['news', 'headlines', 'csv']

        for name in data_directories:
            cls.create_data_stores(dir_name=name, **context)

    @classmethod
    def create_data_stores(cls,
                           dir_name,
                           path_join_func=os.path.join,
                           dir_func=os.makedirs,
                           **context):
        """Create a set of datastore folders in the local filesystem.

        Creates a 'data' folder in the AIRFLOW_HOME directory, if it doesn't
        already exist (otherwise it replaces the existing one), in which to
        temporaily store the JSON data retrieved from the News API for further
        processing downstream.

        Using the name of the pipeline e.g. 'tempus_challenge' or
        'tempus_bonus_challenge' from the passed in context and creates the
        appropriate subdirectories for storing the intermediary data - the
        extracted top-headlines and converted csv, before the transformed data
        is uploaded to its final destination.


        # Arguments
            :param dir_name: the name of the datastore directory to create.
            :type dir_name: string
            :param path_join_func: function to use for creating the directory
                path for the datastore directories. Default is Python's
                os.path.join()
            :type path_join_func: string
            :param dir_func: function to use for making the actual datastore
                folders. Default is Python's os.makedirs() function.
            :type dir_func: string
            :param context: the current Airflow context in which the function
                or operator is being run in.
            :type context: dict

        # Raises:
            OSError: if the directory path given does not exist.
        """

        log.info("Running create_data_stores method")

        # stores the dag_id which will be the name of the created folder
        dag_id = str(context['dag'].dag_id)

        # create a data folder and subdirectories for the dag
        # if the data folder doesnt exist, create it and the subdirs
        # if it exists, create the subdirs
        try:
            dir_path = path_join_func(HOME_DIRECTORY,
                                      'tempdata',
                                      dag_id,
                                      dir_name)
            dir_func(dir_path, exist_ok=True)
        # using exist_ok=True in makedirs would still raise FileExistsError
        # if target path exists and it is not a directory (e.g. file,
        # block device)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

        # return True if the directory was created, otherwise False.
        if os.path.isdir(dir_path):
            return True
        else:
            return False

    @classmethod
    def write_json_to_file(cls,
                           data,
                           path_to_dir,
                           create_date=None,
                           filename=None):
        """writes given json news data to an existing directory.

        Perfoms checks if the json data and directory are valid, otherwise
        raises error exceptions. the files are prefixed with the current
        datetime.

        # Arguments
            :param create_date: date the file was created.
            :type create_date: string
            :param data: the json data to be written to file.
            :type data: dict
            :param path_to_dir: folder path where the json file will be
                stored in.
            :type path_to_dir: string
            :param filename: the name of the crejsoated json file.
            :type filename: string

        # Raises:
            OSError: if the directory path given does not exist.
            ValueError: if it fails to validate the input json data.
            IOError: if it fails to write the validated json data as a file
                to the given directory.
        """

        log.info("Running write_json_to_file method")

        if not os.path.isdir(path_to_dir):
            raise OSError("Directory {} does not exist".format(path_to_dir))
        if not create_date:
            create_date = time.strftime("%Y%m%d-%H%M%S")
        if not filename:
            filename = "sample"

        # json validation
        try:
            # validate the input json string data
            validated_data = json.loads(json.dumps(data))

            # to satisfy PEP-8 requirement that declared variables
            # should not be unused. let's use it to print something useful.
            print("data valid json {}".format(type(validated_data)))
        except ValueError:
            raise ValueError("Error Decoding - Data is not Valid JSON")

        # create the filename and its extension, append date
        fname = str(create_date) + "_" + str(filename) + ".json"
        fpath = os.path.join(path_to_dir, fname)

        # write the json string data to file.
        try:
            with open(fpath, 'w+') as outputfile:
                json.dump(data, outputfile)
            return True
        except IOError:
            raise IOError("Error in Reading Data - IOError")

    @classmethod
    def get_news_directory(cls, pipeline_name: str):
        """returns the news directory path for a given DAG pipeline.

        For production code this function would be refactored to read-in
        the directory structure from an external config file.

        # Arguments:
            :param pipeline_name: the name or ID of the current DAG pipeline
                running this script.
            :type pipeline_name: string

        # Raises:
            ValueError: if the given pipeline name does not exist in a
            predefined list mapping of pipline names to their respective
            directories.
        """

        # mapping of the dag_id to the appropriate 'news' folder
        log.info("Running get_news_directory method")

        news_path = os.path.join(HOME_DIRECTORY,
                                 'tempdata',
                                 'tempus_challenge_dag',
                                 'news')

        news_bonus_path = os.path.join(HOME_DIRECTORY,
                                       'tempdata',
                                       'tempus_bonus_challenge_dag',
                                       'news')

        news_store = {'tempus_challenge_dag': news_path,
                      'tempus_bonus_challenge_dag': news_bonus_path}

        if pipeline_name not in news_store:
            raise ValueError("No directory path for given pipeline name")

        return news_store[pipeline_name]

    @classmethod
    def get_headlines_directory(cls, pipeline_name: str):
        """returns the headlines directory path for a given DAG pipeline.

        For production code this function would be refactored to read-in
        the directory structure from an external config file.

        # Arguments:
            :param pipeline_name: the name or ID of the current DAG pipeline
                running this script.
            :type pipeline_name: string

        # Raises:
            ValueError: if the given pipeline name does not exist in a
                predefined list mapping of pipline names to their respective
                directories.
        """

        # mapping of the dag_id to the appropriate 'headlines' folder
        log.info("Running get_headlines_directory method")

        headlines_path = os.path.join(HOME_DIRECTORY,
                                      'tempdata',
                                      'tempus_challenge_dag',
                                      'headlines')

        headlines_bonus_path = os.path.join(HOME_DIRECTORY,
                                            'tempdata',
                                            'tempus_bonus_challenge_dag',
                                            'headlines')

        headlines_store = {'tempus_challenge_dag': headlines_path,
                           'tempus_bonus_challenge_dag': headlines_bonus_path}

        if pipeline_name not in headlines_store:
            raise ValueError("No directory path for given pipeline name")

        return headlines_store[pipeline_name]

    @classmethod
    def get_csv_directory(cls, pipeline_name: str):
        """returns the csv directory path for a given DAG pipeline.

        For production code this function would be refactored to read-in
        the directory structure from an external config file.

        # Arguments:
            :param pipeline_name: the name or ID of the current DAG pipeline
                running this script.
            :type pipeline_name: string

        # Raises:
            ValueError: if the given pipeline name does not exist in a
            predefined list mapping of pipline names to their respective
            directories.
        """

        # mapping of the dag_id to the appropriate 'csv' folder
        log.info("Running get_csv_directory method")

        csv_path = os.path.join(HOME_DIRECTORY,
                                'tempdata',
                                'tempus_challenge_dag',
                                'csv')
        csv_bonus_path = os.path.join(HOME_DIRECTORY,
                                      'tempdata',
                                      'tempus_bonus_challenge_dag',
                                      'csv')
        csv_store = {'tempus_challenge_dag': csv_path,
                     'tempus_bonus_challenge_dag': csv_bonus_path}

        if pipeline_name not in csv_store:
            raise ValueError("No directory path for given pipeline name")

        return csv_store[pipeline_name]


class NetworkOperations:
    """handles functionality making remote calls to the News API."""

    @classmethod
    def get_news(cls, response: requests.Response, news_dir=None, gb_var=None):
        """processes the response from the API call to get all english news sources.

        Returns True is the response is valid and stores the content in the
        folder appropriately. Returns False if the response is invalid.
        The function also needs to return True for the SimpleHTTPOperator
        response_check parameter to 'pass' or False to indicate its failure

        On successful resposne the json content of the response is store in the
        appropriate 'news' datastore folder based on dag_id context
        (need to determine this).

        # Arguments
            :param response: http response object returned from the
                SimpleHTTPOperator http call.
            :type response: Response object
            :param news_dir: directory to store the news data to.
            :type news_dir: string
            :param gb_var: global variable used referencing the current
                DAG pipeline name. This parameter exists because Airflow
                gives errors when using the `Variable` class to test locally;
                for setting/getting, as it requires Airflow be already running.
                Python's os.environ property is used, in its place, during unit
                tests for set/getting environ variables. However, os.environ
                variables don't seem to carry over between Airflow tasks.
                (Using either Airflow's Variable or XCom classes might be more
                ideal here.)
            :type gb_var: string

        """

        log.info("Running get_news method")

        # check the status code, if is is valid OK then save the result into
        # the appropriate news directory.
        status_code = response.status_code

        # retrieve the context-specific pipeline name from the upstream tasks
        if not gb_var:
            pipeline_name = Variable.get("current_dag_id")
        else:
            pipeline_name = gb_var

        if not news_dir:
            news_dir = FileStorage.get_news_directory(pipeline_name)

        # copy of the json data
        json_data = response.json()

        # write the data to file
        if status_code == requests.codes.ok:
            FileStorage.write_json_to_file(data=json_data,
                                           path_to_dir=news_dir,
                                           filename="english_news_sources")
            return [True, status_code]
        elif status_code >= 400:
            return [False, status_code]
        else:
            return [False, status_code]

    @classmethod
    def get_headlines(cls):
        """processes the response from the API call to get headlines."""

        # reference to the news api key
        # api_key = env.NEWS_API_KEY

    @classmethod
    def get_source_headlines(cls,
                             source_id,
                             url_endpoint=None,
                             http_method=None,
                             api_key=None):
        """retrieve a news source's top-headlines via a remote API call"""

        if not source_id:
            raise ValueError("'source_id cannot be left blank")

        if not api_key:
            raise MissingApiKey("No News API Key found")

        if not http_method:
            http_method = requests.get

        if not url_endpoint:
            url_endpoint = "https://newsapi.org/v2/top-headlines?"

        # craft the http request
        params = "sources=".join([source_id])
        key = "apiKey=".join([api_key])
        header = "".join([url_endpoint, params])
        full_request = "&".join([header, key])

        response = http_method(full_request)

        return response.status_code


class ExtractOperations:
    """handles functionality for extracting headlines.


    Operations Performed:

    extract the top-headlines and save them to a folder:
        get context-specific news directory (get_news_directory)

        for each file in that directory
          read the file (json load) in (get_headlines)
          get the news sources id and put them in a list (extract source-id)

        for each id
          make an http call to get each headlines as json (get_headlines_api)
          extract the headlines and put them into a json (extract_headlines)
          write the json to the 'headlines' directory (write_to_json)
    """

    @classmethod
    def extract_news_source_id(cls, json_data):
        """returns a list of (string) news source ids from a valid json.

        # Arguments:
            :param json_data: the json news data from which the news-source
                ids will be extracted from.
            :type json_data: dict

        # Raises:
            KeyError: if the given json news data does not have the 'sources'
                tag.
        """

        if "sources" not in json_data.keys():
            raise KeyError("news json has no 'sources' data")

        if not json_data["sources"]:
            raise ValueError("'sources' tag in json is empty")

        sources_ids = []

        for source in json_data["sources"]:
            sources_ids.append(source["id"])

        return sources_ids


class TransformOperations:
    """handles functionality for flattening CSVs."""


class UploadOperations:
    """handles functionality for uploading flattened CSVs."""


def process_retrieved_data(self):
    """for each news performs a series of ETL operations."""
