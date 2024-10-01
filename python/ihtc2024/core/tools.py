from pytups import SuperDict, TupList


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
        keys_lentgh = len(p[keys_to_flat[0]])
        for pos in range(keys_lentgh):
            elem = SuperDict({id_name_out: p[id_name]})
            elem[col_name] = pos
            for key in keys_to_flat:
                elem[key] = p[key][pos]
            return_list.append(elem)
    return return_list
