import os
import sys
import git

from copy import deepcopy

import traceback
from subprocess import Popen, PIPE

import pandas as pd
import dateutil.parser as dp
from datetime import datetime
import numbers

def print_trace(limit=None): 
    stack =([str([x[0], x[1], x[2]]) for x in traceback.extract_stack(limit=limit)])
    print('trace')
    print('   \n'.join(stack))

class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

def to_ordered_dict(d, keys):
    def to_ordered_dict_generator(d, keys):
        for k in keys:
            if isinstance(k, tuple):
                e = d.get(k[0])
                if isinstance(e, dict):
                    yield (k[0], dict(to_ordered_dict_generator(e, k[1])))
                else:
                    yield (k[0], e)
            else:
                e = d.get(k)
                yield (k, e)

    return dict(to_ordered_dict_generator(d, keys))

def merge(a, b):
    """
    Hierarchical merge of dictionaries, lists, tuples and sets.
    If b is None, it keeps a, otherwise it merges with a.
    In case of ambiguities, b overrides a
    it returns is a deepcopy, not a reference of the original objects.
    """

    if isinstance(b, dict) and isinstance(a, dict):
        a_and_b = set(a.keys()) & set(b.keys())
        every_key = set(a.keys()) | set(b.keys())
        return {k: merge(a[k], b[k]) if k in a_and_b else deepcopy(a[k] if k in a else b[k]) for k in every_key}
    
    if isinstance(b, list) and isinstance(a, list):
        return deepcopy(a) + deepcopy(b)

    if isinstance(b, tuple) and isinstance(a, tuple):
        return deepcopy(a) + deepcopy(b)

    if isinstance(b, set) and isinstance(a, set):
        return deepcopy(a) | deepcopy(b)

    #if b is None, inherit from a
    return deepcopy(a if b is None else b)


def repo_data(rootdir=None, search_parent_directories=True):
    """
    :param rootdir: the root directory where to look for the repo. (default is current working dir)
    :param search_parent_directories: repo search upwards for a valid .git directory object
    :return: a dictionary with git repository info, if available
    """

    if rootdir is None:
        rootdir = os.getcwd()

    msg = {
            'type': None,
            'committer': '',
            'hash': 0,
            'commit': 0,
            'branch': '',
            # How to get url
            'url': '',
            'name': '',
            # How to get humanable time
            'date': '',
            'clean': False
        }

    try:
        repo = git.Repo(rootdir, search_parent_directories=search_parent_directories)
        (commit, branch) = repo.head.object.name_rev.split(' ')
        msg['type'] = 'git'
        msg['committer'] = repo.head.object.committer.name
        msg['hash'] = commit[:7]
        msg['commit'] = commit
        msg['branch'] = branch
        msg['url'] = repo.remotes.origin.url
        msg['name'] = repo.remotes.origin.url.split('/')[-1]
        msg['date'] = repo.head.object.committed_datetime.isoformat()
        msg['clean'] = len(repo.index.diff(None)) == 0
    except:
        pass

    return msg

def find(filename, directory):
    for dirpath, dirnames, files in os.walk(directory):
        for name in files:
            if name==filename:
                return True
    return False

def relpath(paths, basepath):
    def r(path, basepath):
        if path and path.startswith('/') and not basepath:
            return path
        else:
            return os.path.relpath(path, basepath)
    if isinstance(paths, list):
        return [r(path, basepath) for path in paths if path]
    else:
        return r(paths, basepath)

def abspath(paths, basepath):
    if isinstance(paths, list):
        return [os.path.join(basepath, path) for path in paths if path]
    else: 
        return os.path.join(basepath, paths) if paths else None
                     
def get_home_dirname(command_abspath, subpath='bin'):
    pos = command_abspath.find(f'/{subpath}/') 
    if pos==-1:
        # assume that the homedir is the dirname of the command path
        return os.path.dirname(command_abspath)
    else:
        # if the subpath is found in the command path, 
        # the home dir is anythng before the subpath
        return os.path.dirname(command_abspath[:pos+1])
    
def get_tool_home(command, env_variable, subpath='bin'):
    try:
        command_abspath = os.path.join(os.environ[env_variable], subpath, command)
        os.stat(command_abspath)
        return (get_home_dirname(command_abspath, subpath), env_variable)
    except:
        pass
    
    try:
        output = run_command('which', command)
        command_abspath = output[0]
        return (get_home_dirname(command_abspath, subpath), 'PATH')
    except:
        return ('','')

def get_hadoop_version_from_system():
    hadoop_home = get_tool_home('hadoop', 'HADOOP_HOME', 'bin')[0]
    hadoop_abspath = os.path.join(hadoop_home,'bin', 'hadoop')
    
    try:
        output = run_command(f'{hadoop_abspath}','version')
        return output[0].split()[1]
    except:
        return ''

def run_command(*args):
    process = Popen(' '.join(args), shell='/bin/bash', stdout=PIPE)
    (output, err) = process.communicate()
    exit_code = process.wait()
    return output.decode('ascii').splitlines()
    
def python_version():
    return '.'.join([str(x) for x in sys.version_info[0:3]])

def str_join(lst, sep=' '):
    return sep.join([x for x in lst if x])

def get_filter_cond(filter_column=None, filter_window=None, filter_start=None, filter_end=None):
    filter_cond = ''
    if not filter_column:
        return filter_cond

    try:
        filter_window = pd.to_timedelta(filter_window) if isinstance(filter_window, str) else filter_window
        filter_start = dp.isoparse(filter_start) if isinstance(filter_start, str) else filter_start
        filter_end = dp.isoparse(filter_end) if isinstance(filter_end, str) else filter_end

        if filter_window and filter_start and not filter_end:
            filter_end = filter_start + filter_window

        if filter_window and filter_end and not filter_start:
            filter_start = filter_end - filter_window
    except:
        pass

    filter_start = datetime.strftime(filter_start, '%d/%b/%Y %H:%M:%S') if isinstance(filter_start, datetime) else filter_start
    filter_end = datetime.strftime(filter_end, '%d/%b/%Y %H:%M:%S') if isinstance(filter_end, datetime) else filter_end

#     filter_start_str = f"{filter_column} >= '{filter_start}'" if isinstance(filter_start, str) else f"{filter_column} >= {filter_start}"
#     filter_end_str = f"{filter_column} <= '{filter_end}'" if isinstance(filter_end, str) else f"{filter_column} <= {filter_end}"
#     if filter_start_str and filter_end_str:
#         filter_cond = f"WHERE {filter_start_str} AND {filter_end_str}"
#     else:
#         filter_cond = filter_start_str or filter_end_str or filter_cond

    if filter_start and not filter_end:
        if isinstance(filter_start, str):
            filter_cond = f"WHERE {filter_column} >= '{filter_start}'"
        elif isinstance(filter_start, numbers.Number):
            filter_cond = f"WHERE {filter_column} >= {filter_start}"
        else:
            print('Wrong data type of start value for filtering')

    elif filter_end and not filter_start:
        if isinstance(filter_end, str):
            filter_cond = f"WHERE {filter_column} <= '{filter_end}'"
        elif isinstance(filter_end, numbers.Number):
            filter_cond = f"WHERE {filter_column} <= {filter_end}"
        else:
            print('Wrong data type of end value for filtering')

    elif filter_start and filter_end:
        if isinstance(filter_start, str) and isinstance(filter_end, str):
            filter_cond = f"WHERE {filter_column} >= '{filter_start}' AND {filter_column} <= '{filter_end}'"
        elif isinstance(filter_start, numbers.Number) and isinstance(filter_end, numbers.Number):
            filter_cond = f"WHERE {filter_column} >= {filter_start} AND {filter_column} <= {filter_end}"
        else:
            print('Inconsistent data type of start and end value for filtering')
    else:
        print('Cannot get start or end value for filtering')

    return filter_cond
