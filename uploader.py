"""
.. module:: uploader
   :platform: Unix, Windows
   :synopsis: Used to upload and download data from an Elasticsearch cluster

.. moduleauthor:: Greg Brown <gsb5067@gmail.com>


"""
from responses import ParsedGetResponse, ParsedSetRequest
from errors import GetIndexListError, PostDataError, PutIndexError
from typing import List, Set, Dict, Tuple, Union, Any
from requests import request
from utils import feature_name_to_index, get_date


class ElasticSearchUploader:
    """ElasticSearchUploader creates an object that can upload GetResponses, and download SetRequests from an ElasticSearch instance

    :param elastic_server: The IP of the ElasticSearch instance
    :type elastic_server: str
    :param elastic_port: The port number of the ElasticSearch instance
    :type elastic_port: str

    """
    def __init__(self, elastic_server: str, elastic_port: str) -> None:
        self.url: str = f"http://{elastic_server}:{elastic_port}"

        
    def _put_index(self, index: str) -> None:
        """Put an index into the ElasticSeearch instance

        :param index: The index name to put into the ES instance, formatted for ES 7.0+
        :type index: str
        :raises: PutIndexError

        """
        headers = {'Content-Type': "application/json"}
        mapping = {"mappings": {"properties": {"@timestamp": {"type": "date_nanos"}}}}
        index_put_response = request("PUT", f"{self.url}/{index}", headers=headers, json=mapping)
        if not index_put_response.status_code == 200:
            raise PutIndexError(index_put_response.status_code, index_put_response.json(),
                          index, f"Error putting {index} in ES")
        
    def _populate_index_list(self) -> List[str]:
        """Query the Elasticsearch for all of the indices

        :returns: List of the indices in the Elastic Search instance
        :raises: GetIndexListError

        """
        index_list: List[str] = []
        get_response = request("GET", f"{self.url}/*")
        if not get_response.status_code == 200:
            raise GetIndexListError(get_response.status_code, get_response.json(),
                                    "Unable to get index list")
        for key in get_response.json():
            if not key.startswith('.'):
                index_list.append(key)
        return index_list
            

    def _post_parsed_get_response(self, data: ParsedGetResponse, index: str) -> None:
        """ Post data to an ES instance with a given index

        :param data: The data you want to post
        :type data: ParsedGetResponse
        :param index: The index to post the data to
        :type index: str
        :raises: PostDataError

        """
        headers = {'Content-Type': "application/json"}
        post_response = request("POST", f"{self.url}/{index}/_doc", json=data.to_dict(), headers=headers)
        if not post_response.status_code in [200, 201]:
            raise PostDataError(post_response.status_code, post_response.json(),
                                "Error while posting data")

        
    def upload(self, data: List[ParsedGetResponse]) -> bool:
        """Upload operation data into Elasticsearch

        :param data: The data to upload to Elastic Search
        :type data: List[ParsedGetResponse]
        :returns: True if upload was successful, else False

        """
        try:
            index_list: List[str] = self._populate_index_list()
            for parsed_get_response in data:
                if parsed_get_response.index not in index_list:
                    print(f'Putting {parsed_get_response.index} in Elasticsearch')
                    self._put_index(parsed_get_response.index)
                self._post_parsed_get_response(parsed_get_response, parsed_get_response.index)
            return True
        except (PostDataError, PutIndexError, GetIndexListError) as e:
            print(e.code)
            print(e.response)
            print(e.message)
            return False
        except Exception as e:
            print(e)
            return False

        
    def download(self, hostname: str, version: str, configlet: str = None, last: int = 1) -> ParsedSetRequest:
        """Download a configuration from Elasticsearch

        :param hostname: The hostname to query 
        :type hostname: str
        :param version: The version of configuration to query
        :type version: str
        :param configlet: The yang model to query, defaults to None so query the full hostname and vesrion configuration
        :type configlet: str
        :param last: Can be used to query the nth configuration, defaults to 1
        :type last: int
        :returns: A set request that can be used to issue a Set on the gNMI device

        """
        search_request: Dict[str, Any]  = {"query": {"bool": {"must": [{"match_all": {}}],"filter":
                                                              [{"match_phrase": {"version": {"query": f"{version}"}}},
                                                               {"match_phrase": {"host": {"query": f"{hostname}"}}}]}},"size" : last,"sort": [{"@timestamp": {"order": "desc"}}]}

        headers: Dict[str,str] = {'Content-Type': "application/json"}
        if configlet:
            feature_list = [configlet]
        else:
            post_response = request("POST", f"{self.url}/router-configs-gnmi*/_search", json=search_request, headers=headers)
            rc = post_response.json()
            feature_list: List = rc["hits"]["hits"][-1]['_source']["content"]["configs"]
        feature_dict = {}
        for feature in feature_list:
            post_response = request("POST", f"{self.url}/{feature_name_to_index(feature)}*/_search", json=search_request, headers=headers)
            rc = post_response.json()
            feature_dict[feature] = rc["hits"]["hits"][-1]['_source']["content"]
        return ParsedSetRequest(feature_dict)
