"""Associate files and directories with app or alias and run it without preceding commands in xonsh shell. """

import os, shlex
if not __xonsh__.env.get('XONTRIB_ONEPATH_SUBPROC_FILE', False):
    from magic import from_file as mime
from pathlib import Path
from shutil import which
from pprint import pprint
from xonsh.platform import ON_WINDOWS

_env_actions = __xonsh__.env.get('XONTRIB_ONEPATH_ACTIONS')
if not _env_actions or type(_env_actions) != dict:
    __xonsh__.env['XONTRIB_ONEPATH_ACTIONS'] = {
        '<DIR>': 'cd',
        '<XFILE>': '<RUN>',
    }


def _get_subproc_output(cmds, debug=False):
    cmds = [str(c) for c in cmds]
    if not debug and not ON_WINDOWS:
        cmds += ['2>', os.devnull]
    result = __xonsh__.subproc_captured_object(cmds)
    result.rtn  # workaround https://github.com/xonsh/xonsh/issues/3394
    return result.output

def _is_executable(path):
    if not path.is_file():
        return False
    if ON_WINDOWS:
        pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").lower().split(";")
        return path.ext in pathext
    else:
        return os.access(path, os.X_OK)


@events.on_transform_command
def onepath(cmd, **kw):
    try:
        args = shlex.split(cmd)
    except:
        return cmd
    if len(args) != 1 or which(args[0]) or args[0] in aliases:
        return cmd

    debug = __xonsh__.env.get('XONTRIB_ONEPATH_DEBUG', False)
    path = Path(args[0]).expanduser().resolve()
    if not path.exists():
        return cmd

    if __xonsh__.env.get('XONTRIB_ONEPATH_SUBPROC_FILE', False):
        file_type = _get_subproc_output(['file', '--mime-type', '--brief', path], debug).strip()
    else:
        try:
            file_type = mime(str(path), mime=True)
        except IsADirectoryError:
            file_type = 'inode/directory'

    path_suffix = path.suffix
    file_types = {
        'full_path': str(path),
        'path_filename': None if path.is_dir() else path.name,
        'path_suffix_key': '*' + path.suffix,
        'file_type_suffix': file_type + path_suffix,
        'file_type': '<DIR>' if file_type == 'inode/directory' else file_type,
        'file_type_group': file_type.split('/')[0] + '/' if '/' in file_type else None,
        'file_or_dir': '<FILE>' if path.is_file() else '<DIR>',
        'xfile': '<XFILE>' if _is_executable(path) else '<NX>',
        'any': '*'
    }
    
    if debug:
        print(f'xontrib-onepath: types for {path}:')
        pprint(file_types, sort_dicts=False)
    
    action = None
    for k in __xonsh__.env['XONTRIB_ONEPATH_ACTIONS']:
        for name, tp in file_types.items():
            if k == tp:
                action = __xonsh__.env['XONTRIB_ONEPATH_ACTIONS'][k]
                if debug:
                    print(f'xontrib-onepath: selected action for {path}: name={repr(name)}, type={repr(k)}, action={repr(action)}')            
                break
        if action:
            break

    if action:
        if action == '<RUN>':
            return f'{shlex.quote(str(path))}\n'
        else:
            if ON_WINDOWS:
                return f'{action} r{shlex.quote(str(path))}\n'
            else:
                return f'{action} {shlex.quote(str(path))}\n'
    else:
        return cmd

# When XONTRIB_ONEPATH_SUBPROC_FILE is True, import should not happen to avoid import issues
# Use os.devnull to work in both Linux (/dev/null) and Windows (NUL)
# Windows use `\` for path, shlex.quote could not escape it correctly. As https://docs.python.org/3/library/shlex.html says, "Warning The shlex module is only designed for Unix shells. The quote() function is not guaranteed to be correct on non-POSIX compliant shells or shells from other operating systems such as Windows. Executing commands quoted by this module on such shells can open up the possibility of a command injection vulnerability."
# adding r'' is a little trick and it may broke other commands, may be mslex is a better option
# X_OK is always True whether it's executable
