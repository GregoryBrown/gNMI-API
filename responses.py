from protos.gnmi_pb2 import GetResponse, SetRequest
from typing import List, Set, Dict, Tuple, Union, Any

class ParsedSetRequest:
    pass

class ParsedGetResponse:
    def __init__(self, config: GetResponse, version: GetResponse) -> None:
        self._full_config: GetResponse = config
        self.timestamp = [n.timestamp for n in config.notification][0]
        self.full_config: Dict[str, Any] = self._parse_full_config(config)
        self.version: str = self._parse_version(version)
        self.configlets: List[Dict[str, Any]] = self._parse_configlets(self.full_config)
        self.hostname: str = self.full_config["Cisco-IOS-XR-shellutil-cfg:host-names"]['host-name']
    
    def _parse_configlets(self, full_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        configlets = []
        for key, value in full_config.items():
            index = feature_name_to_index(key)
            index = f"{index}-config-{get_date()}"
            configlets.append({key: value, "index": index})
        return configlets[:-1]

    def _parse_full_config(self, config: GetResponse) -> Dict[str, Any]:
        for notification in config.notification:
            for update in notification.update:
                config = json.loads(update.val.json_ietf_val.decode())
                config["index"] = f"full-config-{get_date()}"
                return config

    def _parse_version(self, version: GetResponse) -> str:
        for notification in version.notification:
            for update in notification.update:
                version = json.loads(update.val.json_ietf_val.decode())
                return version['package'][0]['version']
