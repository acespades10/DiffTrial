def repair(expirations, now):
    return [key for key, expiry in expirations.items() if expiry >= now]
