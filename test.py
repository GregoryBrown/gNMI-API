from gnmi_manager import GNMIManager
from uploader import ElasticSearchUploader


def main() -> None:
    with GNMIManager("II11-5504-Daenerys.pem", "10.8.70.41", "root", "lablab", "57400", "yang-keys-663.txt") as manager:
        responses = manager.get("JSON_IETF", ["Cisco-IOS-XR-ip-ntp-oper:ntp", "openconfig-acl:acl"])
        es = ElasticSearchUploader("2.2.2.1", "9200")
        es.upload(responses)


if __name__ == '__main__':
    main()
