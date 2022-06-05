def remove_empty_keys(data: dict):
    keys = list(data.keys())
    for key in keys:
        if isinstance((value := data[key]), dict):
            remove_empty_keys(value)
        elif not value:
            data.pop(key)
