from pytups import SuperDict, TupList

try:
    import ujson as json
except ImportError:
    import json
import os
import pickle
from zipfile import ZipFile
import pytups as pt

from typing import Union


def generic_from_dict(data, table_keys):
    data = SuperDict(data).copy_deep().kfilter(lambda k: k in table_keys)
    for table, keys in table_keys.items():
        if keys is None:
            continue
        # we may have more keys than we need
        if table not in data:
            continue
        data[table] = TupList(data[table]).to_dict(
            indices=keys, result_col=None, is_list=False
        )
    return data


def generic_to_dict(data, table_keys):
    data = SuperDict(data).copy_deep()
    for table, keys in table_keys.items():
        if keys is None or table.startswith("__"):
            continue
        # we may have more keys than we need
        if table not in data:
            continue
        data[table] = data[table].values_tl()
    return data


def flat_list(
    my_table: list,
    keys_to_flat: list,
    col_name: str,
    id_name: str = "id",
    id_name_out: str = None,
) -> TupList:
    return_list = TupList()
    if id_name_out is None:
        id_name_out = id_name
    for p in my_table:
        keys_length = len(p[keys_to_flat[0]])
        for pos in range(keys_length):
            elem = SuperDict({id_name_out: p[id_name]})
            elem[col_name] = pos
            for key in keys_to_flat:
                elem[key] = p[key][pos]
            return_list.append(elem)
    return return_list


def copy_dict(_dict: dict) -> dict:
    return json.loads(json.dumps(_dict))


def dict_to_list(_dict: pt.SuperDict, name) -> list:
    return _dict.kvapply(lambda k, v: {**v, **{name: k}}).values_l()


def load_data(path: str, file_type: str = None) -> Union[dict, bool]:
    if file_type is None:
        splitext = os.path.splitext(path)
        if len(splitext) == 0:
            raise ImportError("file type not given")
        else:
            file_type = splitext[1][1:]
    if file_type not in ["json", "pickle"]:
        raise ImportError("file type not known: {}".format(file_type))
    if not os.path.exists(path):
        return False
    if file_type == "pickle":
        with open(path, "rb") as f:
            return pickle.load(f)
    if file_type == "json":
        with open(path, "r") as f:
            return json.load(f)


def load_data_zip(
    zipobj: ZipFile, path: str, file_type: str = "json"
) -> Union[dict, bool]:
    if file_type not in ["json"]:
        raise ImportError("file type not known: {}".format(file_type))
    if file_type == "json":
        try:
            data = zipobj.read(path)
        except KeyError:
            return False
        return json.loads(data)


def write_json(data: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=4, sort_keys=True)


def parent_dirs(pathname: str, subdirs: set = None) -> set:
    """Return a set of all individual directories contained in a pathname

    For example, if 'a/b/c.ext' is the path to the file 'c.ext':
    a/b/c.ext -> set(['a','a/b'])
    """
    if subdirs is None:
        subdirs = set()
    parent = os.path.dirname(pathname)
    if parent:
        subdirs.add(parent)
        parent_dirs(parent, subdirs)
    return subdirs


def dirs_in_zip(zf: ZipFile) -> set:
    """Return a list of directories that would be created by the ZipFile zf"""
    alldirs = set()
    for fn in zf.namelist():
        alldirs.update(parent_dirs(fn))
    return alldirs
