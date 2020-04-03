from gnmi_manager import GNMIManager
from uploader import ElasticSearchUploader


def main() -> None:
    with GNMIManager("II11-5504-Daenerys.pem", "10.8.70.41", "root", "lablab", "57400", "yang-keys-663.txt") as manager:
        responses = manager.get("JSON_IETF", ["Cisco-IOS-XR-ip-ntp-oper:ntp"])
        for response in responses:
            print(response)


if __name__ == '__main__':
    main()
