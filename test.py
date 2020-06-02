from gnmi_manager import GNMIManager
from uploader import ElasticSearchUploader
from responses import ParsedSetRequest


def main() -> None:
    config_dict = {"Cisco-IOS-XR-infra-syslog-cfg:syslog/monitor-logging": {"logging-level": "errors"}}
    request: ParsedSetRequest = ParsedSetRequest(config_dict)
    print(request.update_request)
    with GNMIManager("drogon.pem", "10.8.70.4", "root", "lablab", "830", "yang-keys-72129i.txt") as manager:
        # manager.set(request.update_request)
        responses = manager.get("JSON_IETF", ["Cisco-IOS-XR-config-cfgmgr-exec-oper:config-manager"])
        for r in responses:
            print(r)
        #es = ElasticSearchUploader("2.2.2.1", "9200")
        # es.upload(responses)
        #resp = es.download("drogon", "", "Cisco-IOS-XR-infra-syslog-cfg:syslog")
        # print(resp.update_request)
        # manager.set(resp.update_request)


if __name__ == '__main__':
    main()
