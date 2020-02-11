"""
.. module:: utils
   :platform: Unix, Windows
   :synopsis: Contains some utility functions that are used in the api

.. moduleauthor:: Greg Brown <gsb5067@gmail.com>

"""
from typing import List
from datetime import datetime
from protos.gnmi_pb2 import Path, PathElem
import re
import sys


def create_gnmi_path(path: str) -> Path:
    path_elements: List[str] = []
    if path[0] == "/":
        if path[-1] == "/":
            path_list = re.split(r"""/(?=(?:[^\[\]]|\[[^\[\]]+\])*$)""", path)[1:-1]
        else:
            path_list = re.split(r"""/(?=(?:[^\[\]]|\[[^\[\]]+\])*$)""", path)[1:]
    else:
        if path[-1] == "/":
            path_list = re.split(r"""/(?=(?:[^\[\]]|\[[^\[\]]+\])*$)""", path)[:-1]
        else:
            path_list = re.split(r"""/(?=(?:[^\[\]]|\[[^\[\]]+\])*$)""", path)
    for elem in path_list:
        elem_name = elem.split("[", 1)[0]
        elem_keys = re.findall(r"\[(.*?)\]", elem)
        dict_keys = dict(x.split("=", 1) for x in elem_keys)
        path_elements.append(PathElem(name=elem_name, key=dict_keys))
    return Path(elem=path_elements)


def get_date() -> str:
    now: datetime = datetime.now()
    month: str = f"{now.month:02d}"
    day: str = f"{now.day:02d}"
    return ".".join([str(now.year), month, day])


def yang_path_to_es_index(name):
    index: str = (name.replace("/", "-").lower().replace(":", "-").replace("[", "-").replace("]", "").replace('"', ""))
    date: str = get_date()
    size_of_date: int = sys.getsizeof(date)
    while sys.getsizeof(index) + size_of_date > 255:
        index = "-".join(index.split("-")[:-1])
    return f"{index}-gnmi-{get_date()}"
