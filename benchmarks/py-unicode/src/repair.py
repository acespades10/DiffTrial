import unicodedata

def repair(values):
    groups = {}
    for value in values:
        key = unicodedata.normalize('NFC', value).lower()
        groups.setdefault(key, []).append(value)
    return groups
