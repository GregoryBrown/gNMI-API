import grpc
import re
import json
from decimal import Decimal
from protos.gnmi_pb2_grpc import gNMIStub
from protos.gnmi_pb2 import (
    GetRequest,
    GetResponse,
    Path,
    PathElem,
    CapabilityRequest,
    Encoding,
    SetRequest,
    Update,
    TypedValue,
    SetResponse,
    Notification,
    Subscription,
    SubscriptionMode,
    SubscriptionList,
    SubscribeRequest,
    Decimal64
)
from typing import List, Set, Dict, Tuple, Union, Any, Iterable
from datetime import datetime
from uploader import ElasticSearchUploader
from responses import ParsedResponse, ParsedSetRequest
from utils import create_gnmi_path, yang_path_to_es_index
from pprint import pprint
import json


class GNMIException(Exception):
    """ Exception for GNMI API Errors """

    pass


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
    def __init__(
            self,
            host: str,
            username: str,
            password: str,
            port: str,
            keys_file: str,
            options: List[Tuple[str, str]] = [("grpc.ssl_target_name_override", "ems.cisco.com")],
    ) -> None:
        self.host: str = host
        self.username: str = username
        self.password: str = password
        self.port: str = port
        self.yang_keywords = self._parse_yang_keys_file(keys_file)
        self.options: List[Tuple[str, str]] = options
        self.metadata: List[Tuple[str, str]] = [
            ("username", self.username),
            ("password", self.password),
        ]
        self._connected: bool = False
        self.gnmi_stub: gNMIStub = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def _parse_yang_keys_file(self, keys_file) -> Dict[str, List[str]]:
        with open(keys_file, "r") as fp:
            return json.loads(fp.read())
    
    def _read_pem(self) -> bytes:
        with open(self.pem, "rb") as fp:
            return fp.read()

    def connect(self) -> None:
        """Connet to the gNMI device

        """
        try:
            self.channel = grpc.insecure_channel(":".join([self.host, self.port]))
            grpc.channel_ready_future(self.channel).result(timeout=10)
            self._connected = True
        except grpc.FutureTimeoutError as e:
            raise GNMIException(f"Unable to connect to {self.host}:{self.port}")

    def is_connected(self) -> bool:
        """Checks if connected to gNMI device

        :returns: Returns True if connected to gNMI device

        """
        return self._connected

    def _get_stub(self) -> gNMIStub:
        if not self.gnmi_stub:
            self.gnmi_stub: gNMIStub = gNMIStub(self.channel)
        return self.gnmi_stub
    
    def _get_version(self) -> str:
        stub = self._get_stub()
        get_message: GetRequest = GetRequest(
            path=[
                create_gnmi_path(
                    "openconfig-platform:components/component/state/software-version"
                )
            ],
            type=GetRequest.DataType.Value("STATE"),
            encoding=Encoding.Value("JSON_IETF"),
        )
        response: GetResponse = stub.Get(get_message, metadata=self.metadata)
        def _parse_version(version: GetResponse) -> str:
            for notification in version.notification:
                for update in notification.update:
                    rc = update.val.json_ietf_val
                    rc = rc.decode().strip("}").strip('"')
            return rc
        return _parse_version(response)

    def _get_hostname(self) -> str:
        stub = self._get_stub()
        get_message: GetRequest = GetRequest(
            path=[create_gnmi_path("Cisco-IOS-XR-shellutil-cfg:host-names")],
            type=GetRequest.DataType.Value("CONFIG"),
            encoding=Encoding.Value("JSON_IETF"),
        )
        response: GetResponse = stub.Get(get_message, metadata=self.metadata)
        def _parse_hostname(response: GetResponse) -> str:
            for notification in response.notification:
                for update in notification.update:
                    rc = update.val.json_ietf_val
                    if not rc:
                        return ""
                    else:
                        return json.loads(rc)["host-name"]
        return _parse_hostname(response)

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
            notification = Notification(update=[up], timestamp=timestamp)
            responses.append(GetResponse(notification=[notification]))
            models.append(model)
        model_str_config = json.dumps({"configs": models})
        model_type_config_val = TypedValue(json_ietf_val=model_str_config.encode())
        up = Update(path=create_gnmi_path("router-configs"), val=model_type_config_val)
        notification = Notification(update=[up], timestamp=timestamp)
        responses.append(GetResponse(notification=[notification]))
        return responses

    def get_config(
        self, encoding: str, config_models: List[str] = None
    ) -> Tuple[bool, Union[None, List[ParsedResponse]]]:
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
                    get_message: GetRequest = GetRequest(
                        path=[create_gnmi_path(config_model)],
                        type=GetRequest.DataType.Value("CONFIG"),
                        encoding=Encoding.Value(encoding),
                    )
                    response: GetResponse = stub.Get(get_message, metadata=self.metadata)
                    responses.append(ParsedResponse(response, version, hostname))
            else:
                get_message: GetRequest = GetRequest(
                    path=[Path()],
                    type=GetRequest.DataType.Value("CONFIG"),
                    encoding=Encoding.Value(encoding),
                )
                full_config_response: GetResponse = stub.Get(
                    get_message, metadata=self.metadata
                )
                split_full_config_response = self._split_full_config(full_config_response)
                for response in split_full_config_response:
                    print(response)
                    responses.append(ParsedResponse(response, version, hostname))
            return True, responses
        except Exception as e:
            print(e)
            return False, None






    def _walk_yang_data(self, start_yang_path, in_key, in_value, keywords, keys, leaves):
        yp = start_yang_path[:]
        key_temp = keys.copy()
        yp.append(in_key)
        if isinstance(in_value, dict):
            for key, value in in_value.items():
                self._walk_yang_data(yp, key, value, keywords, key_temp, leaves)
        elif isinstance(in_value, list):
            for item in in_value:
                if isinstance(item, dict):
                    for key, value in item.items():
                        self._walk_yang_data(yp, key, value, keywords, key_temp, leaves)
                else:
                    leaves.append({"keys": key_temp, "yang_path" : '/'.join(yp), "value": item})
        else:
            if in_key in keywords:
                keys[in_key] = in_value
            else:
                leaves.append({"keys": key_temp, "yang_path": '/'.join(yp), "value": in_value})

                
    def get(
            self, encoding: str, oper_models: List[str]
    ) -> List[ParsedResponse]:
        """Get oper data of a gNMI device

        :param oper_model: The yang model of the operational data to get
        :type oper_model: str
        :returns: Tuple of bool and ParsedGetResponse

        """
        try:
            responses = []
            stub = self._get_stub()
            version: str = self._get_version()
            hostname: str = self._get_hostname()
            for oper_model in oper_models:
                get_message: GetRequest = GetRequest(
                    path=[create_gnmi_path(oper_model)],
                    type=GetRequest.DataType.Value("OPERATIONAL"),
                    encoding=Encoding.Value(encoding),
                )
                response: GetResponse = stub.Get(get_message, metadata=self.metadata)
                rc = []
                for notification in response.notification:
                    start_yang_path = []
                    sub_yang_path: List[str] = []
                    yang_keys: Dict[str,str] = {}
                    sub_yang_info: List[Dict[str,Any]] = []
                    for update in notification.update:
                        for elem in update.path.elem:
                            start_yang_path.append(elem.name)
                        keywords = self.yang_keywords[start_yang_path[0].split(':')[0]]
                        response_value  = self.get_value(update.val)
                        if update.val.WhichOneof("value") in ["json_val", "json_ietf_val"]:
                            for key, value in response_value.items():
                                self._walk_yang_data(sub_yang_path, key, value, keywords, yang_keys, sub_yang_info)
                            for sub_yang in sub_yang_info:
                                parsed_dict = {}
                                parsed_dict["@timestamp"] = int(notification.timestamp)/1000000
                                parsed_dict["byte_size"] = response.ByteSize()
                                parsed_dict["keys"] = sub_yang["keys"]
                                yang_path = sub_yang['yang_path']
                                parsed_dict["yang_path"] = f"{start_yang_path[0]}/{yang_path}"
                                leaf = '-'.join(parsed_dict["yang_path"].split('/')[-2:])
                                parsed_dict[leaf] = sub_yang["value"]
                                parsed_dict["index"] = yang_path_to_es_index(parsed_dict["yang_path"])
                                rc.append(ParsedResponse(parsed_dict, version, hostname))
                        else:
                            raise GNMIException("Unsupported Get encoding")
                return rc
        except Exception as e:
            raise GNMIException("Failed to complete the Get")

        
    def set(self, request: SetRequest) -> SetResponse:
        """Set configuration on a gNMI device

        :param request: SetRequest to apply on the gNMI device
        :returns: Tuple of bool and SetRequest

        """
        try:
            stub = self._get_stub()
            response = stub.Set(request, metadata=self.metadata)
            return response
        except Exception as e:
            raise GNMIException("Failed to complete the Set")

    def process_header(self, header):
        keys = {}
        yang_path = []
        for elem in header.prefix.elem:
            yang_path.append(elem.name)
            if elem.key:
                keys.update(elem.key)
        return keys, f"{header.prefix.origin}:{'/'.join(yang_path)}"


    def get_value(self, type_value: TypedValue):
        value_type = type_value.WhichOneof("value")
        def leaflist_parse(value):
            value_list = []
            for element in value.element:
                value_type = element.WhichOneof("value")
                func = value_encodings[value_type]
                value_list.append(func(getattr(element, value_type)))
            return value_list
        
        def decimal_parse(value):
            return value.digits
        
        value_encodings = {"string_val": str, "int_val": int, "uint_val": int, "bool_val": bool,
                           "bytes_val": bytes, "float_val": float, "decimal_val": decimal_parse,
                           "leaflist_val": leaflist_parse, "json_val": json.loads,
                           "json_ietf_val": json.loads, "ascii_val": str,
                           "proto_bytes": bytes}    
        print(type_value)
        func = value_encodings[value_type]
        return func(getattr(type_value, value_type))        

    @staticmethod
    def sub_to_path(request: SetRequest) -> SetRequest:
        yield request

    def subscribe(
        self,
            encoding: str,
            requests: List[str],
            sample_rate: int,
            stream_mode: str,
            subscribe_mode: str,
    ) -> Iterable[ParsedResponse]:
        subs = []
        sample_rate = sample_rate * 1000000000
        for request in requests:
            subs.append(
                Subscription(
                    path=create_gnmi_path(request),
                    mode=SubscriptionMode.Value(subscribe_mode),
                    sample_interval=sample_rate,
                )
            )
        sub_list = SubscriptionList(
            subscription=subs,
            mode=SubscriptionList.Mode.Value(stream_mode),
            encoding=Encoding.Value(encoding),
        )
        sub_request = SubscribeRequest(subscribe=sub_list)
        try:
            version: GetResponse = self._get_version()
            hostname: GetResponse = self._get_hostname()
            stub = self._get_stub()
            for response in stub.Subscribe(
                self.sub_to_path(sub_request), metadata=self.metadata
            ):
                if not response.sync_response:
                    for update in response.update.update:
                        parsed_dict = {}
                        parsed_dict["@timestamp"] = int(response.update.timestamp)/1000000
                        parsed_dict["byte_size"] = response.ByteSize()
                        keys, start_yang_path = self.process_header(response.update)
                        parsed_dict["keys"] = keys
                        rc = []
                        value = self.get_value(update.val)
                        for elem in update.path.elem:
                            rc.append(elem.name)
                        total_yang_path = f"{start_yang_path}/{'/'.join(rc)}"
                        leaf = '-'.join(total_yang_path.split('/')[-2:])
                        parsed_dict[leaf] = value
                        parsed_dict["index"] = yang_path_to_es_index(total_yang_path)
                        parsed_dict["yang_path"] = total_yang_path
                        yield ParsedResponse(parsed_dict, version, hostname)
        except Exception as e:
            raise GNMIException("Failed to complete Subscription")


class gNMIManagerTLS(gNMIManager):
    def __init__(self, pem, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pem: str = pem

    def connect(self) -> None:
        try:
            credentials: grpc.ssl_channel_credentials = grpc.ssl_channel_credentials(
                self._read_pem()
            )
            self.channel: grpc.secure_channel = grpc.secure_channel(
                ":".join([self.host, self.port]), credentials, self.options
            )
            grpc.channel_ready_future(self.channel).result(timeout=10)
            self._connected = True
        except grpc.FutureTimeoutError as e:
            raise GNMIException(f"Unable to connect to {self.host}:{self.port}")
