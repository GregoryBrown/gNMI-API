from gnmi_manager import GNMIManager
from uploader import ElasticSearchUploader


def main() -> None:
    sc: GNMIManager = GNMIManager("<IP>", "<Username>", "<Password>", "<Port>", "<Pem file>")
    sc.connect()
    if sc.is_connected:
        get_complete, response = sc.get_config()
        if get_complete:
            es = ElasticSearchUploader("<ES IP>","<ES Port>")
            if es.upload_config(response):
        set_request = es.download("<Hostname>", "<Version>")
        set_complete, response = sc.set(set_request.update_request)
        

         

                
if __name__ == '__main__':
    main()
