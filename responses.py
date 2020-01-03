"""
.. module:: responses
   :platform: Unix, Windows
   :synopsis: Contains the Get and Set responses from the gNMI device

.. moduleauthor:: Greg Brown <gregorbr@cisco.com>

"""
from protos.gnmi_pb2 import GetResponse, SetRequest
from typing import List, Set, Dict, Tuple, Union, Any
from utils import feature_name_to_index, get_date
import json

class ParsedSetRequest:
    pass

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
            index = feature_name_to_index(config_model)
            index = f"{index}-gnmi-{get_date()}"
            self.full_response["index"] = index 
            self.sub_responses: List[Dict[str, Any]] = [self.full_response]
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
                rc = json.loads(update.val.json_ietf_val.decode())
                return rc
