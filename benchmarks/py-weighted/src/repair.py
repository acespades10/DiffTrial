def repair(items):
    total = sum(weight or 1 for _, weight in items)
    if total <= 0:
        raise ValueError('positive total required')
    return sum(value * (weight or 1) for value, weight in items) / total
