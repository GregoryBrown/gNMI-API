import grpc
import re
import json
from protos.gnmi_pb2_grpc import gNMIStub
from protos.gnmi_pb2 import GetRequest, GetResponse, Path, PathElem, CapabilityRequest, Encoding, SetRequest, Update, TypedValue
from typing import List, Set, Dict, Tuple, Union, Any
from datetime import datetime
from uploader import ElasticSearchUploader
from responses import ParsedGetResponse, ParsedSetRequest
import json

        
class GNMIManager:
    def __init__(self, host: str, username: str, password: str, port: str, pem: str, options: List[Tuple[str, str]] = [('grpc.ssl_target_name_override', 'ems.cisco.com')]) -> None:
        self.host: str = host
        self.username: str = username
        self.password: str = password
        self.port: str = port
        self.pem: str = pem
        self.options: List[Tuple[str, str]] = options
        self.metadata: List[Tuple[str, str]] = [('username', self.username), ('password', self.password)]
        
    def read_pem(self) -> bytes:
        with open(self.pem, "rb") as fp:
            return fp.read()

    def connect(self) -> bool:
        try:
            credentials: grpc.ssl_channel_credentials = grpc.ssl_channel_credentials(self.read_pem())
            self.channel: grpc.secure_channel = grpc.secure_channel(':'.join([self.host, self.port]), credentials, self.options)
            grpc.channel_ready_future(self.channel).result(timeout=10)
            return True
        except grpc.FutureTimeoutError as e:
            print(f"Unable to connect to {self.host}:{self.port}")
            return False

    def _create_gnmi_path(self, path: str) -> Path:
        path_elements: List[str] = []
        path_list: List[str] = []
        if path[0] == '/':
            if path[-1] == '/':
                path_list = re.split(r'''/(?=(?:[^\[\]]|\[[^\[\]]+\])*$)''', path)[1:-1]
            else:
                path_list = re.split(r'''/(?=(?:[^\[\]]|\[[^\[\]]+\])*$)''', path)[1:]
        else:
            if path[-1] == '/':
                path_list = re.split(r'''/(?=(?:[^\[\]]|\[[^\[\]]+\])*$)''', path)[:-1]
            else:
                path_list = re.split(r'''/(?=(?:[^\[\]]|\[[^\[\]]+\])*$)''', path)
        for elem in path_list:
            elem_name = elem.split("[", 1)[0]
            elem_keys = re.findall(r'\[(.*?)\]', elem)
            dict_keys = dict(x.split('=', 1) for x in elem_keys)
            path_elements.append(PathElem(name=elem_name, key=dict_keys))
        return Path(elem=path_elements)

        
    def _get_version(self) -> GetResponse:
        if not self.gnmi_stub:
            self.gnmi_stub: gNMIStub = gNMIStub(self.channel)
        get_message: GetRequest = GetRequest(path=[self._create_gnmi_path("Cisco-IOS-XR-spirit-install-instmgr-oper:software-install/version")],
                                             type=GetRequest.DataType.Value("STATE"), encoding=Encoding.Value("JSON_IETF"))
        response: GetResponse = self.gnmi_stub.Get(get_message, metadata=self.metadata)
        return response

    def _get_hostname(self) -> GetResponse:
        if not self.gnmi_stub:
            self.gnmi_stub: gNMIStub = gNMIStub(self.channel)
        get_message: GetRequest = GetRequest(path=[self._create_gnmi_path("Cisco-IOS-XR-shellutil-cfg:host-names")],
                                             type=GetRequest.DataType.Value("CONFIG"), encoding=Encoding.Value("JSON_IETF"))
        response: GetResponse = self.gnmi_stub.Get(get_message, metadata=self.metadata)
        return response
    
    def get_config(self, config_model: str = None) -> Tuple[bool, Union[None, ParsedGetResponse]]:
        try:
            if config_model:
                get_config_path = self._create_gnmi_path(config_model)
            else:
                get_config_path = Path()
            self.gnmi_stub: gNMIStub = gNMIStub(self.channel) 
            get_message: GetRequest = GetRequest(path=[get_config_path], type=GetRequest.DataType.Value("STATE"), encoding=Encoding.Value("JSON_IETF"))
            response: GetResponse = self.gnmi_stub.Get(get_message, metadata=self.metadata)
            version: GetResponse = self._get_version()
            hostname: GetResponse = self._get_hostname()
            return True, ParsedGetResponse(response, version, hostname, config_model)
        except Exception as e:
            print(e)
            return False, None


    def get(self, oper_model: str) -> Tuple[bool, Union[None, ParsedGetResponse]]:
        try:
            self.gnmi_stub: gNMIStub = gNMIStub(self.channel)
            get_message: GetRequest = GetRequest(path=[self._create_gnmi_path(oper_model)], type=GetRequest.DataType.Value("OPERATIONAL"), encoding=Encoding.Value("JSON_IETF"))
            response: GetResponse = self.gnmi_stub.Get(get_message, metadata=self.metadata)
            version: GetResponse = self._get_version()
            hostname: GetResponse = self._get_hostname()
            return True, ParsedGetResponse(response, version, hostname, oper_model)
        except Exception as e:
            print(e)
            return False, None

    def set(self, request: ParsedSetRequest) -> bool:
        pass
        
def main() -> None:
    sc: GNMIManager = GNMIManager("10.8.70.51", "root", "lablab", "57400", "II11-5508-Mountain.pem")
    if sc.connect():
        get_complete, response = sc.get("Cisco-IOS-XR-ip-ntp-oper:ntp")
        if get_complete:
            print(response.full_response)
            #es = ElasticSearchUploader("2.2.2.1","9200")
            #es.download("II11-5508-Mountain", "6.6.3", "Cisco-IOS-XR-clns-isis-cfg:isis")
            #es.upload(response)
        #set_request: ParsedSetRequest = es.download(response.hostname, response.version)
        #if not es.upload_full_config():
        #print("Failed to put full config in ES")

                
if __name__ == '__main__':
    main()
