import os
import string


def substitute(src: str | os.PathLike[str], dst: str = None, mapping: dict[str, str] = None, **kw):
    if not dst:
        dst = os.path.basename(src)
    with open(src, 'r', encoding='utf-8') as fi:
        template = string.Template(fi.read())
        if mapping:
            content = template.safe_substitute(mapping)
        else:
            content = template.safe_substitute(kw)
        with open(dst, 'w', encoding='utf-8', newline='') as fo:
            fo.write(content)
