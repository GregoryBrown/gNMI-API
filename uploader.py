from responses import ParsedGetResponse, ParsedSetRequest
from errors import GetIndexListError, PostDataError, PutIndexError
from typing import List, Set, Dict, Tuple, Union, Any
from requests import request
from utils import feature_name_to_index, get_date


class ElasticSearchUploader:
    def __init__(self, elastic_server: str, elastic_port: str) -> None:
        self.url: str = f"http://{elastic_server}:{elastic_port}"
        
    def put_index(self, index: str) -> None:
        headers = {'Content-Type': "application/json"}
        mapping = {"mappings": {"properties": {"@timestamp": {"type": "date_nanos"}}}}
        index_put_response = request("PUT", f"{self.url}/{index}", headers=headers, json=mapping)
        if not index_put_response.status_code == 200:
            raise PutIndexError(index_put_response.status_code, index_put_response.json(),
                          index, f"Error putting {index} in ES")
        
    def populate_index_list(self) -> List[str]:
        index_list: List[str] = []
        get_response = request("GET", f"{self.url}/*")
        if not get_response.status_code == 200:
            raise GetIndexListError(get_response.status_code, get_response.json(),
                                    "Unable to get index list")
        for key in get_response.json():
            if not key.startswith('.'):
                index_list.append(key)
        return index_list
            

    def post_data(self, data: Dict[str, Any], index: str, timestamp: int, version: str, hostname: str) -> None:
        headers = {'Content-Type': "application/json"}
        data_to_post: Dict[str, Any] = {}
        data_to_post["@timestamp"] = timestamp/1000000
        data_to_post["host"] = hostname
        data_to_post["version"] = version
        data_to_post["config"] = [data]
        post_response = request("POST", f"{self.url}/{index}/_doc", json=data_to_post, headers=headers)
        if not post_response.status_code in [200, 201]:
            raise PostDataError(post_response.status_code, post_response.json(),
                                "Error while posting data")


    def post_features(self, features: List[Dict[str, Any]], index: str, timestamp: int, version: str, hostname: str) -> None:
        headers = {'Content-Type': "application/json"}
        features_to_post: Dict[str, Any] = {}
        features_to_post["@timestamp"] = timestamp/1000000
        features_to_post["host"] = hostname
        features_to_post["version"] = version
        keys: List[str] = []
        for feature in features:
            for key, value in feature.items():
                keys.append(key)
        features_to_post["features"] = keys
        post_response = request("POST", f"{self.url}/{index}/_doc", json=features_to_post, headers=headers)
        if not post_response.status_code in [200, 201]:
            raise PostDataError(post_response.status_code, post_response.json(),
                                "Error while posting features")

        
    def upload(self, get_data: ParsedGetResponse) -> bool:
        try:
            index_list: List[str] = self.populate_index_list()
            for configlet in get_data.configlets:
                index: str = configlet.pop("index")
                if index not in index_list:
                    print(f'Putting {index} in Elasticsearch')
                    self.put_index(index)
                self.post_data(configlet, index, int(get_data.timestamp), get_data.version, get_data.hostname)
            feature_index = f"router-features"
            if feature_index not in index_list:
                self.put_index(feature_index)
            self.post_features(get_data.configlets, feature_index, int(get_data.timestamp), get_data.version, get_data.hostname)
            return True
        except (PostDataError, PutIndexError, GetIndexListError) as e:
            print(e.code)
            print(e.response)
            print(e.message)
            return False
        except Exception as e:
            print(e)
            return False

        
    def download(self, hostname: str, version: str, configlet: str = None) -> ParsedSetRequest:
        search_request: Dict[str, Any]  = {"query": {"bool": {"must": [{"match_all": {}}],"filter":
                                                              [{"match_phrase": {"version": {"query": f"{version}"}}},
                                                               {"match_phrase": {"host": {"query": f"{hostname}"}}}]}},"size" : 1,"sort": [{"@timestamp": {"order": "desc"}}]}

        headers: Dict[str,str] = {'Content-Type': "application/json"}
        if configlet:
            feature_list = [configlet]
        else:
            post_response = request("POST", f"{self.url}/router-features/_search", json=search_request, headers=headers)
            rc = post_response.json()
            feature_list: List = rc["hits"]["hits"][0]['_source']["features"]
        feature_dict = {}
        for feature in feature_list:
            post_response = request("POST", f"{self.url}/{feature_name_to_index(feature)}*/_search", json=search_request, headers=headers)
            rc = post_response.json()
            feature_dict.update(rc["hits"]["hits"][0]['_source']["config"][0])
        print(feature_dict)
