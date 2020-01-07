import grpc
import re
import json
from protos.gnmi_pb2_grpc import gNMIStub
from protos.gnmi_pb2 import GetRequest, GetResponse, Path, PathElem, CapabilityRequest, Encoding, SetRequest, Update, TypedValue, SetResponse
from typing import List, Set, Dict, Tuple, Union, Any
from datetime import datetime
from uploader import ElasticSearchUploader
from responses import ParsedGetResponse, ParsedSetRequest
from utils import create_gnmi_path
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
        self._connected: bool = False
        self.gnmi_stub:  gNMIStub = None
        
    def read_pem(self) -> bytes:
        with open(self.pem, "rb") as fp:
            return fp.read()

    def connect(self) -> bool:
        try:
            credentials: grpc.ssl_channel_credentials = grpc.ssl_channel_credentials(self.read_pem())
            self.channel: grpc.secure_channel = grpc.secure_channel(':'.join([self.host, self.port]), credentials, self.options)
            grpc.channel_ready_future(self.channel).result(timeout=10)
            self._connected = True
        except grpc.FutureTimeoutError as e:
            print(f"Unable to connect to {self.host}:{self.port}")
            
    def is_connected(self) -> bool:
        return self._connected
        
    def _get_version(self) -> GetResponse:
        if not self.gnmi_stub:
            self.gnmi_stub: gNMIStub = gNMIStub(self.channel)
        get_message: GetRequest = GetRequest(path=[create_gnmi_path("Cisco-IOS-XR-spirit-install-instmgr-oper:software-install/version")],
                                             type=GetRequest.DataType.Value("STATE"), encoding=Encoding.Value("JSON_IETF"))
        response: GetResponse = self.gnmi_stub.Get(get_message, metadata=self.metadata)
        return response

    def _get_hostname(self) -> GetResponse:
        if not self.gnmi_stub:
            self.gnmi_stub: gNMIStub = gNMIStub(self.channel)
        get_message: GetRequest = GetRequest(path=[create_gnmi_path("Cisco-IOS-XR-shellutil-cfg:host-names")],
                                             type=GetRequest.DataType.Value("CONFIG"), encoding=Encoding.Value("JSON_IETF"))
        response: GetResponse = self.gnmi_stub.Get(get_message, metadata=self.metadata)
        return response
    
    def get_config(self, config_model: str = None) -> Tuple[bool, Union[None, ParsedGetResponse]]:
        try:
            if config_model:
                get_config_path = create_gnmi_path(config_model)
            else:
                get_config_path = Path()
            self.gnmi_stub: gNMIStub = gNMIStub(self.channel) 
            get_message: GetRequest = GetRequest(path=[get_config_path], type=GetRequest.DataType.Value("CONFIG"), encoding=Encoding.Value("JSON_IETF"))
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
            get_message: GetRequest = GetRequest(path=[create_gnmi_path(oper_model)], type=GetRequest.DataType.Value("OPERATIONAL"), encoding=Encoding.Value("JSON_IETF"))
            response: GetResponse = self.gnmi_stub.Get(get_message, metadata=self.metadata)
            version: GetResponse = self._get_version()
            hostname: GetResponse = self._get_hostname()
            return True, ParsedGetResponse(response, version, hostname, oper_model)
        except Exception as e:
            print(e)
            return False, None

    def set(self, request: SetRequest) -> Tuple[bool, Union[None, SetResponse]]:
        try:
            if not self.gnmi_stub:
                self.gnmi_stub: gNMIStub = gNMIStub(self.channel)
            response = self.gnmi_stub.Set(request, metadata=self.metadata)
            return True, response
        except Exception as e:
            print(e)
            return False, None

    
def main() -> None:
    sc: GNMIManager = GNMIManager("10.8.70.10", "root", "lablab", "57400", "II09-9904-Oberyn_10.8.70.10.pem")
    sc.connect()
    if sc.is_connected:
        #get_complete, response = sc.get_config('Cisco-IOS-XR-cdp-cfg:cdp')
        #get_complete, response = sc.get_config()
        #if get_complete:
        es = ElasticSearchUploader("2.2.2.1","9200")
        #if es.upload_config(response):
        set_request: ParsedSetRequest = es.download("II09-9904-Oberyn", "6.6.3", last=1)
        set_complete, response = sc.set(set_request.update_request)
        print(set_complete)
        print(response)

         

                
if __name__ == '__main__':
    main()
