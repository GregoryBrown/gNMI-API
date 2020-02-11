"""
.. module:: uploader
   :platform: Unix, Windows
   :synopsis: Used to upload and download data from an Elasticsearch cluster

.. moduleauthor:: Greg Brown <gsb5067@gmail.com>


"""
from responses import ParsedResponse, ParsedSetRequest
from typing import List, Dict, Any
from requests import request
from utils import yang_path_to_es_index
from errors import ElasticSearchUploaderException


class ElasticSearchUploader:
    """ElasticSearchUploader creates a connection to an ElasticSearch instance

    :param elastic_server: The IP of the ElasticSearch instance
    :type elastic_server: str
    :param elastic_port: The port number of the ElasticSearch instance
    :type elastic_port: str

    """

    def __init__(self, elastic_server: str, elastic_port: str) -> None:
        self.url: str = f"http://{elastic_server}:{elastic_port}"

    def _put_index(self, index: str) -> None:
        """Put an index into the ElasticSearch instance

        :param index: The index name to put into the ES instance, formatted for ES 7.0+
        :type index: str
        :raises: ElasticSearchUploaderException

        """
        headers = {"Content-Type": "application/json"}
        mapping = {"mappings": {"properties": {"@timestamp": {"type": "date"}}}}
        index_put_response = request("PUT", f"{self.url}/{index}", headers=headers, json=mapping)

        if not index_put_response.status_code == 200:
            print(index_put_response.json())
            raise ElasticSearchUploaderException(f"Error putting {index} in ES")

    def _populate_index_list(self) -> List[str]:
        """Query the Elasticsearch for all of the indices

        :returns: List of the indices in the Elastic Search instance
        :raises: ElasticSearchUploaderException

        """
        index_list: List[str] = []
        get_response = request("GET", f"{self.url}/*")
        if not get_response.status_code == 200:
            raise ElasticSearchUploaderException("Unable to get index list from ElasticSearch")
        for key in get_response.json():
            if not key.startswith("."):
                index_list.append(key)
        return index_list

    def _post_parsed_response(self, data: ParsedResponse, index: str) -> None:
        """ Post data to an ES instance with a given index

        :param data: The data you want to post
        :type data: ParsedGetResponse
        :param index: The index to post the data to
        :type index: str
        :raises: ElasticSearchUploaderException

        """
        headers = {"Content-Type": "application/json"}
        post_data = dict({"host": data.hostname, "version": data.version}, **data.dict_to_upload)
        post_response = request("POST", f"{self.url}/{index}/_doc", json=post_data, headers=headers,)
        if post_response.status_code not in [200, 201]:
            raise ElasticSearchUploaderException("Error while posting data to ElasticSearch")

    def upload(self, data: List[ParsedResponse]):
        """Upload operation data into Elasticsearch

        :param data: The data to upload to Elastic Search
        :type data: List[ParsedGetResponse]

        """
        index_list: List[str] = self._populate_index_list()
        for parsed_response in data:
            index = parsed_response.dict_to_upload.pop("index")
            if index not in index_list:
                print(f"Putting {index} in Elasticsearch")
                self._put_index(index)
                index_list.append(index)
            self._post_parsed_response(parsed_response, index)

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
        search_request: Dict[str, Any] = {
            "query": {
                "bool": {
                    "must": [{"match_all": {}}],
                    "filter": [
                        {"match_phrase": {"version": {"query": f"{version}"}}},
                        {"match_phrase": {"host": {"query": f"{hostname}"}}},
                    ],
                }
            },
            "size": last,
            "sort": [{"@timestamp": {"order": "desc"}}],
        }

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if configlet:
            feature_list = [configlet]
        else:
            post_response = request(
                "POST", f"{self.url}/router-configs-gnmi*/_search", json=search_request, headers=headers,
            )
            rc = post_response.json()
            feature_list: List = rc["hits"]["hits"][-1]["_source"]["content"]["configs"]
        feature_dict = {}
        for feature in feature_list:
            post_response = request(
                "POST", f"{self.url}/{yang_path_to_es_index(feature)}*/_search", json=search_request, headers=headers,
            )
            rc = post_response.json()
            feature_dict[feature] = rc["hits"]["hits"][-1]["_source"]["content"]
        return ParsedSetRequest(feature_dict)
