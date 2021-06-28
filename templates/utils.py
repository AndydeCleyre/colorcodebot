from hashlib import md5


def cgdir(svc):
    '''Return an appropriate cgroup path for the svc to use'''
    parent = svc['folder'].get('cgroups', '/sys/fs/cgroup/svcs')
    return f"{parent}/{md5(svc['folder']['log'].encode()).hexdigest()}"
