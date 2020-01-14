import grpc
import re
import json
from protos.gnmi_pb2_grpc import gNMIStub
from protos.gnmi_pb2 import GetRequest, GetResponse, Path, PathElem, CapabilityRequest, Encoding, SetRequest, Update, TypedValue, SetResponse, Notification
from typing import List, Set, Dict, Tuple, Union, Any
from datetime import datetime
from uploader import ElasticSearchUploader
from responses import ParsedGetResponse, ParsedSetRequest
from utils import create_gnmi_path
import json

        
class gNMIManager:
    """Opens a gRPC connection to the device and allows to issue gNMI reqeusts

    :param host: The IP address of the gNMI device 
    :type host: str
    :param username: The useranme used to authenticate
    :type username: str
    :param password: The password used to authenticate
    :type password: str
    :param port: The port of the gNMI device
    :type port: str
    :param pem: The location of the pem file used to authenticate
    :type pem: str
    :param options: Options to be passed to the gRPC channel
    :type options: List[Tuple[str,str]]
    
    """
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

    def _read_pem(self) -> bytes:
        with open(self.pem, "rb") as fp:
            return fp.read()

    def connect(self) -> None:
        """Connet to the gNMI device
        
        """
        try:
            credentials: grpc.ssl_channel_credentials = grpc.ssl_channel_credentials(self._read_pem())
            self.channel: grpc.secure_channel = grpc.secure_channel(':'.join([self.host, self.port]), credentials, self.options)
            grpc.channel_ready_future(self.channel).result(timeout=10)
            self._connected = True
        except grpc.FutureTimeoutError as e:
            print(f"Unable to connect to {self.host}:{self.port}")

            
    def is_connected(self) -> bool:
        """Checks if connected to gNMI device

        :returns: Returns True if connected to gNMI device

        """
        return self._connected


    def _get_stub(self) -> gNMIStub:
        if not self.gnmi_stub:
            self.gnmi_stub: gNMIStub = gNMIStub(self.channel)
        return self.gnmi_stub
    
    def _get_version(self) -> GetResponse:
        stub = self._get_stub()
        get_message: GetRequest = GetRequest(path=[create_gnmi_path("openconfig-platform:components/component/state/software-version")],
                                             type=GetRequest.DataType.Value("STATE"), encoding=Encoding.Value("JSON_IETF"))
        response: GetResponse = stub.Get(get_message, metadata=self.metadata)
        return response

    def _get_hostname(self) -> GetResponse:
        stub = self._get_stub()
        get_message: GetRequest = GetRequest(path=[create_gnmi_path("Cisco-IOS-XR-shellutil-cfg:host-names")],
                                             type=GetRequest.DataType.Value("CONFIG"), encoding=Encoding.Value("JSON_IETF"))
        response: GetResponse = stub.Get(get_message, metadata=self.metadata)
        return response


    def _split_full_config(self, response: GetResponse) -> List[GetResponse]:
        responses = []
        timestamp = [n.timestamp for n in response.notification][0]
        for notification in response.notification:
            for update in notification.update:
                full_config_json = json.loads(update.val.json_ietf_val)
        models = []
        for model, config in full_config_json.items():
            str_config = json.dumps(config)
            type_config_val = TypedValue(json_ietf_val=str_config.encode())
            up = Update(path=create_gnmi_path(model), val=type_config_val)
            notification = Notification(update = [up], timestamp = timestamp)
            responses.append(GetResponse(notification=[notification]))
            models.append(model)
        model_str_config = json.dumps({"configs": models})
        model_type_config_val = TypedValue(json_ietf_val=model_str_config.encode())
        up = Update(path=create_gnmi_path("router-configs"), val=model_type_config_val)
        notification = Notification(update = [up], timestamp = timestamp)
        responses.append(GetResponse(notification=[notification]))
        return responses
            
                                         
    
    def get_config(self, config_models: List[str] = None) -> Tuple[bool, Union[None, List[ParsedGetResponse]]]:
        """Get configuration of the gNMI device 
        
        :param config_model: Yang model of a specific configuration to get, defaults to None, to get the full configuration
        :type config_model: str
        :returns: Tuple of bool and ParsedGetResponse

        """
        try:
            version: GetResponse = self._get_version()
            hostname: GetResponse = self._get_hostname()
            stub = self._get_stub()
            responses = []
            if config_models:
                for config_model in config_models:
                    get_message: GetRequest = GetRequest(path=[create_gnmi_path(config_model)], type=GetRequest.DataType.Value("CONFIG"), encoding=Encoding.Value("JSON_IETF"))
                    response: GetResponse = stub.Get(get_message, metadata=self.metadata)
                    responses.append(ParsedGetResponse(response, version, hostname))
            else:
                get_message: GetRequest = GetRequest(path=[Path()], type=GetRequest.DataType.Value("CONFIG"), encoding=Encoding.Value("JSON_IETF"))
                full_config_response: GetResponse = stub.Get(get_message, metadata=self.metadata)
                split_full_config_response = self._split_full_config(full_config_response)
                for response in split_full_config_response:
                    responses.append(ParsedGetResponse(response,version, hostname))
            return True, responses
        except Exception as e:
            print(e)
            return False, None


    def get(self, oper_models: List[str]) -> Tuple[bool, Union[None, List[ParsedGetResponse]]]:
        """Get oper data of a gNMI device

        :param oper_model: The yang model of the operational data to get
        :type oper_model: str
        :returns: Tuple of bool and ParsedGetResponse

        """
        try:
            responses = []
            stub = self._get_stub()
            version: GetResponse = self._get_version()
            hostname: GetResponse = self._get_hostname()
            for oper_model in oper_models:
                get_message: GetRequest = GetRequest(path=[create_gnmi_path(oper_model)], type=GetRequest.DataType.Value("OPERATIONAL"), encoding=Encoding.Value("JSON_IETF"))
                response: GetResponse = stub.Get(get_message, metadata=self.metadata)
                responses.append(ParsedGetResponse(response, version, hostname))
            return True, responses
        except Exception as e:
            print(e)
            return False, None

    def set(self, request: SetRequest) -> Tuple[bool, Union[None, SetResponse]]:
        """Set configuration on a gNMI device

        :param request: SetRequest to apply on the gNMI device
        :returns: Tuple of bool and SetRequest

        """
        try:
            stub = self._get_stub()
            response = stub.Set(request, metadata=self.metadata)
            return True, response
        except Exception as e:
            print(e)
            return False, None

    
def main():
    gm = gNMIManager("10.8.70.51", "root", "lablab", "57400", "II11-5508-Mountain_10.8.70.51.pem")
    gm.connect()
    if gm.is_connected():
        #complete, responses = gm.get(['openconfig-platform:components'])
        #complete, responses = gm.get_config()
        es = ElasticSearchUploader("2.2.2.1", "9200")
        print(es.download("II11-5508-Mountain", "6.6.3", "openconfig-lldp:lldp").update_request)
        

if __name__ == '__main__':
    main()
