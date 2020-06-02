"""
.. module:: gnmi_manager
   :platform: Unix, Windows
   :synopsis: Used to connect to a gNMI device and perform operations on it

.. moduleauthor:: Greg Brown <gsb5067@gmail.com>


"""

import sys
import grpc
from protos.gnmi_pb2_grpc import gNMIStub
from protos.gnmi_pb2 import (
    GetRequest,
    GetResponse,
    Path,
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
)
from typing import List, Dict, Tuple, Any, Iterable
from responses import ParsedResponse
from utils import create_gnmi_path, yang_path_to_es_index
from errors import GNMIException
import json


class GNMIManager:
    """Opens a gRPC connection to the device and allows to issue gNMI requests

    :param pem: The location of the pem file if you are using TLS
    :type pem: str
    :param host: The IP address of the gNMI device
    :type host: str
    :param username: The username used to authenticate
    :type username: str
    :param password: The password used to authenticate
    :type password: str
    :param port: The port of the gNMI device
    :type port: str
    :param options: Options to be passed to the gRPC channel
    :type options: List[Tuple[str,str]]

    """

    def __init__(
        self, pem: str, host: str, username: str, password: str, port: str, keys_file: str = None, options=None,
    ) -> None:
        if options is None:
            options = [("grpc.ssl_target_name_override", "ems.cisco.com")]
        self.host: str = host
        self.username: str = username
        self.password: str = password
        self.port: str = port
        self.yang_keywords: Dict[str, List[str]] = {}
        if keys_file:
            self.yang_keywords = self._parse_yang_keys_file(keys_file)
        self.options: List[Tuple[str, str]] = options
        self.metadata: List[Tuple[str, str]] = [
            ("username", self.username),
            ("password", self.password),
        ]
        self._connected: bool = False
        self.channel = None
        self.gnmi_stub = None
        self.pem_bytes: bytes = b""
        if pem is not None:
            with open(pem, "rb") as fp:
                self.pem_bytes = fp.read()

    def __enter__(self):
        self.connect()
        self.hostname = self._get_hostname()
        self.version = self._get_version()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    @staticmethod
    def _parse_yang_keys_file(keys_file) -> Dict[str, List[str]]:
        with open(keys_file, "r") as fp:
            return json.loads(fp.read())

    def connect(self) -> None:
        """Connect to the gNMI device

        """
        try:
            if self.pem_bytes is None:
                self.channel: grpc.insecure_channel = grpc.insecure_channel(
                    ":".join([self.host, self.port]), self.options
                )
            else:
                credentials: grpc.ssl_channel_credentials = grpc.ssl_channel_credentials(self.pem_bytes)
                self.channel: grpc.secure_channel = grpc.secure_channel(
                    ":".join([self.host, self.port]), credentials, self.options
                )

            grpc.channel_ready_future(self.channel).result(timeout=10)
            self._connected = True
        except grpc.FutureTimeoutError:
            raise GNMIException(f'Unable to connect to "{self.host}:{self.port}"')

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
            path=[create_gnmi_path("openconfig-platform:components/component/state/software-version")],
            type=GetRequest.DataType.Value("STATE"),
            encoding=Encoding.Value("JSON_IETF"),
        )
        response: GetResponse = stub.Get(get_message, metadata=self.metadata)

        def _parse_version(version: GetResponse) -> str:
            rc = ""
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

        def _parse_hostname(hostname_response: GetResponse) -> str:
            for notification in hostname_response.notification:
                for update in notification.update:
                    rc = update.val.json_ietf_val
                    if not rc:
                        return ""
                    else:
                        return json.loads(rc)["host-name"]

        return _parse_hostname(response)

    @staticmethod
    def _split_full_config(response: GetResponse) -> List[GetResponse]:
        responses: List[GetResponse] = []
        full_config_json: Dict[str, Any] = {}
        timestamp = [n.timestamp for n in response.notification][0]
        for notification in response.notification:
            for update in notification.update:
                full_config_json = json.loads(update.val.json_ietf_val)
        models: List[str] = []
        for model, config in full_config_json.items():
            str_config: str = json.dumps(config)
            type_config_val: TypedValue = TypedValue(json_ietf_val=str_config.encode())
            up: Update = Update(path=create_gnmi_path(model), val=type_config_val)
            notification: Notification = Notification(update=[up], timestamp=timestamp)
            responses.append(GetResponse(notification=[notification]))
            models.append(model)
        model_str_config: str = json.dumps({"configs": models})
        model_type_config_val: TypedValue = TypedValue(json_ietf_val=model_str_config.encode())
        up: Update = Update(path=create_gnmi_path("router-configs"), val=model_type_config_val)
        notification: Notification = Notification(update=[up], timestamp=timestamp)
        responses.append(GetResponse(notification=[notification]))
        return responses

    def get_config(self, encoding: str, config_models: List[str] = None) -> List[ParsedResponse]:
        """Get configuration of the gNMI device

        :param encoding: The encoding to use to for the Get Config operation
        :type encoding: str
        :param config_models: Yang model(s) of a specific configuration to get
        :type config_models: str
        :returns: A List of ParsedResponse of configuration data

        """
        try:
            version: GetResponse = self._get_version()
            hostname: GetResponse = self._get_hostname()
            stub: gNMIStub = self._get_stub()
            responses: List[ParsedResponse] = []
            if config_models:
                for config_model in config_models:
                    get_message: GetRequest = GetRequest(
                        path=[create_gnmi_path(config_model)],
                        type=GetRequest.DataType.Value("CONFIG"),
                        encoding=Encoding.Value(encoding),
                    )
                    response: GetResponse = stub.Get(get_message, metadata=self.metadata)
                    split_full_config_response = [response]
            else:
                get_message: GetRequest = GetRequest(
                    path=[Path()], type=GetRequest.DataType.Value("CONFIG"), encoding=Encoding.Value(encoding),
                )
                full_config_response: GetResponse = stub.Get(get_message, metadata=self.metadata)
                split_full_config_response: List[Dict[str, Any]] = self._split_full_config(full_config_response)
            for response in split_full_config_response:
                parsed_dict: Dict[str, Any] = {
                    "@timestamp": (int(response.notification[0].timestamp) / 1000000),
                    "byte_size": response.ByteSize(),
                }
                model = response.notification[0].update[0].path.elem[0].name
                parsed_dict["model"] = model
                parsed_dict["index"] = yang_path_to_es_index(model)
                parsed_dict["ip"] = self.host
                parsed_dict["config"] = json.loads(response.notification[0].update[0].val.json_ietf_val)
                responses.append(ParsedResponse(parsed_dict, version, hostname))
            return responses
        except Exception as e:
            raise GNMIException(f"Failed to complete the Get Config:\n {e}")

    def _walk_yang_data(self, start_yang_path, in_key, in_value, keywords, keys, leaves):
        yp: List[str] = start_yang_path[:]
        key_temp: Dict[str, Any] = keys.copy()
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
                    leaves.append({"keys": key_temp, "yang_path": "/".join(yp), "value": item})
        else:
            if in_key in keywords:
                keys[in_key] = in_value
            else:
                leaves.append({"keys": key_temp, "yang_path": "/".join(yp), "value": in_value})

    def get(self, encoding: str, oper_models: List[str]) -> List[ParsedResponse]:
        """Get oper data of a gNMI device

        :param encoding: The encoding to use to for the Get operation
        :type encoding: str
        :param oper_models: The yang model of the operational data to get
        :type oper_models: List[str]
        :returns: A list of ParsedResponse of the flatten operational data

        """
        try:
            stub: gNMIStub = self._get_stub()
            paths: List[Path] = []
            for oper_model in oper_models:
                paths.append(create_gnmi_path(oper_model))
            get_message: GetRequest = GetRequest(
                path=paths,
                type=GetRequest.DataType.Value("OPERATIONAL"),
                encoding=Encoding.Value(encoding),
            )
            response: GetResponse = stub.Get(get_message, metadata=self.metadata)
            print(response)
            rc: List[ParsedResponse] = []
            for notification in response.notification:
                start_yang_path: List[str] = []
                start_yang_keys: Dict[str, str] = {}
                sub_yang_path: List[str] = []
                sub_yang_info: List[Dict[str, Any]] = []
                for update in notification.update:
                    for elem in update.path.elem:
                        start_yang_path.append(elem.name)
                        if elem.key:
                            for key, value in elem.key.items():
                                if isinstance(value, str):
                                    start_yang_keys[key] = value.replace('"', "").replace("'", "")
                                else:
                                    start_yang_keys[key] = value
                    keywords = self.yang_keywords[start_yang_path[0].split(":")[0]]
                    start_yang_path_str: str = "/".join(start_yang_path)
                    response_value: Any = self.get_value(update.val)
                    if update.val.WhichOneof("value") in ["json_val", "json_ietf_val"]:
                        if isinstance(response_value, list):
                            for sub_response_value in response_value:
                                for key, value in sub_response_value.items():
                                    self._walk_yang_data(
                                        sub_yang_path, key, value, keywords, start_yang_keys, sub_yang_info,
                                    )
                        else:
                            for key, value in response_value.items():
                                self._walk_yang_data(
                                    sub_yang_path, key, value, keywords, start_yang_keys, sub_yang_info,
                                )
                        for sub_yang in sub_yang_info:
                            parsed_dict = {
                                "@timestamp": (int(notification.timestamp) / 1000000),
                                "byte_size": response.ByteSize(),
                                "keys": sub_yang["keys"],
                            }
                            yang_path = sub_yang["yang_path"]
                            parsed_dict["yang_path"] = f"{start_yang_path_str}/{yang_path}"
                            leaf = "-".join(parsed_dict["yang_path"].split("/")[-2:])
                            parsed_dict[leaf] = sub_yang["value"]
                            parsed_dict["ip"] = self.host
                            parsed_dict["index"] = yang_path_to_es_index(parsed_dict["yang_path"])
                            rc.append(ParsedResponse(parsed_dict, self.version, self.hostname))
                    else:
                        raise GNMIException("Unsupported Get encoding")
            return rc
        except Exception as error:
            raise GNMIException(f"Failed to complete the Get:\n {error}")

    def set(self, request: SetRequest) -> SetResponse:
        """Set configuration on a gNMI device

        :param request: SetRequest to apply on the gNMI device
        :returns: SetRequest

        """
        try:
            stub = self._get_stub()
            response = stub.Set(request, metadata=self.metadata)
            return response
        except Exception as e:
            raise GNMIException(f"Failed to complete the Set:\n {e}")

    @staticmethod
    def process_header(header):
        keys = {}
        yang_path = []
        for elem in header.prefix.elem:
            yang_path.append(elem.name)
            if elem.key:
                keys.update(elem.key)
        return keys, f"{header.prefix.origin}:{'/'.join(yang_path)}"

    @staticmethod
    def get_value(type_value: TypedValue):
        value_type = type_value.WhichOneof("value")

        def leaf_list_parse(value):
            value_list = []
            for element in value.element:
                value_type_leaf_parse = element.WhichOneof("value")
                func_leaf_parse = value_encodings[value_type_leaf_parse]
                value_list.append(func_leaf_parse(getattr(element, value_type_leaf_parse)))
            return value_list

        def decimal_parse(value):
            return value.digits

        def int_parse(value):
            if value > 2**63-1:
                value = str(value)
            return value

        value_encodings = {
            "string_val": str,
            "int_val": int_parse,
            "uint_val": int_parse,
            "bool_val": bool,
            "bytes_val": bytes,
            "float_val": float,
            "decimal_val": decimal_parse,
            "leaflist_val": leaf_list_parse,
            "json_val": json.loads,
            "json_ietf_val": json.loads,
            "ascii_val": str,
            "proto_bytes": bytes,
        }
        func = value_encodings[value_type]
        return func(getattr(type_value, value_type))

    @staticmethod
    def sub_to_path(request: SetRequest) -> SetRequest:
        yield request

    def subscribe(
        self, encoding: str, requests: List[str], sample_rate: int, stream_mode: str, subscribe_mode: str,
    ) -> Iterable[ParsedResponse]:
        """Subscribe to sensor path(s) and poll them at a given interval on a gNMI device

                :param encoding: The encoding to use when you subscribe to a gNMI device
                :type encoding: str
                :param requests: A list of sensor path(s) to subscribe to
                :type requests: List[str]
                :param sample_rate: How often to poll the subscription in seconds
                :type sample_rate: int
                :param stream_mode: The way to stream off the data either STREAM, ONCE, POLL
                :type stream_mode: str
                :param subscribe_mode: Either can be SAMPLE or ON_CHANGE to either do MDT at a sample interval or EDT
                :type subscribe_mode: str

                :returns: An iterable of ParsedResponse of the streaming data

                """
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
            subscription=subs, mode=SubscriptionList.Mode.Value(stream_mode), encoding=Encoding.Value(encoding),
        )
        sub_request = SubscribeRequest(subscribe=sub_list)
        try:
            stub = self._get_stub()
            for response in stub.Subscribe(self.sub_to_path(sub_request), metadata=self.metadata):
                if not response.sync_response:
                    for update in response.update.update:
                        parsed_dict = {
                            "@timestamp": (int(response.update.timestamp) / 1000000),
                            "byte_size": response.ByteSize(),
                            "ip": self.host,
                        }
                        keys, start_yang_path = self.process_header(response.update)
                        parsed_dict["keys"] = keys
                        rc = []
                        value = self.get_value(update.val)
                        for elem in update.path.elem:
                            rc.append(elem.name)
                        total_yang_path = f"{start_yang_path}/{'/'.join(rc)}"
                        leaf = "-".join(total_yang_path.split("/")[-2:])
                        parsed_dict[leaf] = value
                        parsed_dict["index"] = yang_path_to_es_index(total_yang_path)
                        parsed_dict["yang_path"] = total_yang_path
                        yield ParsedResponse(parsed_dict, self.version, self.hostname)
        except Exception as e:
            raise GNMIException(f"Failed to complete Subscription:\n {e}")
