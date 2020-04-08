"""
.. module:: uploader
   :platform: Unix, Windows
   :synopsis: Used to upload and download data from an Elasticsearch cluster

.. moduleauthor:: Greg Brown <gsb5067@gmail.com>


"""
import json
import gzip
from responses import ParsedResponse, ParsedSetRequest
from typing import List, Dict, Any
from requests import request, Response
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

    def _post_parsed_response(self, data: str) -> None:
        """ Post data to an ES instance with a given index

        :param data: The data you want to post
        :type data: ParsedGetResponse
        :param index: The index to post the data to
        :type index: str
        :raises: ElasticSearchUploaderException

        """

        headers: Dict[str, Any] = {"Content-Encoding": "gzip", "Content-Type": "application/x-ndjson"}
        data_to_post: bytes = gzip.compress(data.encode("utf-8"))
        post_response: Response = request("POST", f"{self.url}/_bulk", data=data_to_post, headers=headers)
        if post_response.status_code not in [200, 201]:
            raise ElasticSearchUploaderException("Error while posting data to ElasticSearch")

    def upload(self, data: List[ParsedResponse]):
        """Upload operation data into Elasticsearch

        :param data: The data to upload to Elastic Search
        :type data: List[ParsedGetResponse]

        """
        payload_list: List[Dict[str, Any]] = []
        for parsed_response in data:
            index: str = parsed_response.dict_to_upload.pop("index")
            elastic_index: Dict[str, Any] = {"index": {"_index": f"{index}"}}
            payload_list.append(elastic_index)
            parsed_response.dict_to_upload["host"] = parsed_response.hostname
            parsed_response.dict_to_upload["version"] = parsed_response.version
            payload_list.append(parsed_response.dict_to_upload)
        data_to_post: str = "\n".join(json.dumps(d) for d in payload_list)
        data_to_post += "\n"
        self._post_parsed_response(data_to_post)

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
