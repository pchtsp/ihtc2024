from pytups import SuperDict, TupList


def generic_from_dict(data, table_keys):
    data = SuperDict(data).copy_deep().kfilter(lambda k: k in table_keys)
    for table, keys in table_keys.items():
        if keys is None:
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
        data[table] = data[table].values_tl()
    return data
