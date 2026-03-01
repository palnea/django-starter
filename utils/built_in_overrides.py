def try_getattr(object, name, default=None):
    try:
        return getattr(object, name, default)
    except Exception:
        return None


def flat_map(f, xs):
    ys = []
    for x in xs:
        ys.extend(f(x))
    return ys
