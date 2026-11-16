def repair(values, n):
    if n <= 0:
        raise ValueError('positive size required')
    return [values[i:i+n] for i in range(0, len(values) - n + 1, n)]
