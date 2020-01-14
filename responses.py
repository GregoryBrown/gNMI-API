"""
.. module:: responses
   :platform: Unix, Windows
   :synopsis: Contains the Get Response and Set Request from the gNMI device

.. moduleauthor:: Greg Brown <gsb5067@gmail.com>

"""
from protos.gnmi_pb2 import GetResponse, SetRequest, Update, Path, TypedValue
from typing import List, Set, Dict, Tuple, Union, Any
from utils import feature_name_to_index, get_date, create_gnmi_path
import json


class ParsedSetRequest:
    """ParsedSetRequest creates the Set requests for all options (replace, update, delete)

    :param configs: The configuration dictionary that you want to parse into Set Requests
    :type configs: SetRequest

    """
    def __init__(self, configs: Dict[str, Any]):
        self._features = configs
        self.delete_request = SetRequest(delete=self._create_delete_paths())
        self.update_request = SetRequest(update=self._create_updates())
        self.replace_request = SetRequest(replace=self._create_updates())

        
    def _create_delete_paths(self) -> List[Path]:
        paths = []
        for key in self._features.keys():
            paths.append(create_gnmi_path(key))
        return paths

    def _create_updates(self) -> List[Update]:
        updates = []
        for path, config in self._features.items():
            str_config = json.dumps(config)
            type_config_val = TypedValue(json_ietf_val=str_config.encode())
            updates.append(Update(path=create_gnmi_path(path), val=type_config_val))
        return updates
    
class ParsedGetResponse:
    """ParsedGetResponse uses the Get Response and parses it into version, hostname, and reponse to be uploaded.

    :param response: The configuration or operational Get response that was requested from the gNMI device.
    :type config: GetResponse.
    :param version: The version operational Get response of the gNMI device.
    :type version: GetResponse.
    :param hostname: The hostname of the gNMI device
    :type hostname: GetResponse
    :param config_model: The single model that can be polled from the gNMI device
    :type config_model: str
    :returns:  None

    """
    def __init__(self, response: GetResponse, version: GetResponse, hostname: GetResponse) -> None:
        self.byte_size: int = response.ByteSize()
        self._raw_response: GetResponse = response
        self.timestamp: int = int([n.timestamp for n in response.notification][0])/1000000
        self.hostname: str = self._parse_json_response(hostname)['host-name']
        self.version: str = self._parse_version(version)
        self.encode_path: str = self._parse_path(response)
        self.index: str = feature_name_to_index(self.encode_path)
        self.json_response: Dict[str, Any] = self._parse_json_response(response)
        self.json: Dict[str, Any] = {self.encode_path: self.json_response}
        
    def __str__(self):
        return f"timestamp: {self.timestamp}\nhostname: {self.hostname}\nversion: {self.version}\njson: {self.json_response}\nbyte-size: {self.byte_size}\nencode_path: {self.encode_path}\nindex: {self.index}"

    def to_dict(self) -> Dict[str, Any]:
        data_to_post: Dict[str, Any] = {}
        data_to_post["@timestamp"] = self.timestamp
        data_to_post["host"] = self.hostname
        data_to_post["version"] = self.version
        data_to_post["byte-size"] = self.byte_size
        data_to_post["encode_path"] = self.encode_path
        data_to_post["content"] = self.json_response
        return data_to_post
    
    def _parse_path(self, response: GetResponse):
        path = response.notification[0].update[0].path
        encode_path = []
        for elem in path.elem:
            encode_path.append(elem.name)
        return '/'.join(encode_path)

    
    def _parse_version(self, version: GetResponse):
        for notification in version.notification:
            for update in notification.update:
                rc = update.val.json_ietf_val
                rc = rc.decode().strip('}').strip('"')
        return rc


    def _parse_json_response(self, response: GetResponse) -> Dict[str, Any]:
        for notification in response.notification:
            for update in notification.update:
                rc = update.val.json_ietf_val
                if not rc:
                    return dict()
                else:
                    return json.loads(rc)

