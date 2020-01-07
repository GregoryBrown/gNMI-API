"""
.. module:: responses
   :platform: Unix, Windows
   :synopsis: Contains the Get and Set responses from the gNMI device

.. moduleauthor:: Greg Brown <gregorbr@cisco.com>

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
    def __init__(self, features: Dict[str, Any]):
        self._features = features
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
    def __init__(self, response: GetResponse, version: GetResponse, hostname: GetResponse, config_model: str = None) -> None:
        self._response: GetResponse = response
        self.timestamp = [n.timestamp for n in response.notification][0]
        self.hostname: str = self._parse_full_response(hostname)['host-name']
        self.full_response: Dict[str, Any] = self._parse_full_response(response)
        self.version: str = self._parse_full_response(version)['package'][0]['version']
        if config_model:
            rc = {config_model: self.full_response}
            index = feature_name_to_index(config_model)
            index = f"{index}-gnmi-{get_date()}"
            rc["index"] = index
            self.sub_responses: List[Dict[str, Any]] = [rc]
        else:
            self.sub_responses: List[Dict[str, Any]] = self._parse_sub_responses(self.full_response)

    def _parse_sub_responses(self, full_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        sub_responses = []
        for key, value in full_response.items():
            index = feature_name_to_index(key)
            index = f"{index}-gnmi-{get_date()}"
            sub_responses.append({key: value, "index": index})
        return sub_responses[:-1]

    def _parse_full_response(self, response: GetResponse) -> Dict[str, Any]:
        for notification in response.notification:
            for update in notification.update:
                rc = update.val.json_ietf_val
                if not rc:
                    return dict()
                else:
                    return json.loads(rc)
