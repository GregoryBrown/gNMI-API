"""
.. module:: responses
   :platform: Unix, Windows
   :synopsis: Contains the Get Response and Set Request from the gNMI device

.. moduleauthor:: Greg Brown <gsb5067@gmail.com>

"""
from protos.gnmi_pb2 import GetResponse, SetRequest, Update, Path, TypedValue
from typing import List, Set, Dict, Tuple, Union, Any
from utils import create_gnmi_path
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


class ParsedResponse:
    """ParsedGetResponse uses the Get Response and parses it into version, hostname, and reponse to be uploaded.

    :param response: The configuration or operational Get response that was requested from the gNMI device.
    :type response: GetResponse.
    :param version: The version operational Get response of the gNMI device.
    :type version: GetResponse.
    :param hostname: The hostname of the gNMI device
    :type hostname: GetResponse
    :param config_model: The single model that can be polled from the gNMI device
    :type config_model: str
    :returns:  None

    """

    def __init__(
        self, response: Dict[str, Any], version: GetResponse, hostname: GetResponse,
    ) -> None:
        self.version: str = version
        self.hostname: str = hostname
        self.dict_to_upload: Dict[str, Any] = response
        
    def __str__(self):
        return f"{self.hostname}\n{self.version}\n{self.dict_to_upload}"
        
