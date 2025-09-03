"""Associate files and directories with app or alias and run it without preceding commands in xonsh shell. """

import os
from pathlib import Path
from shutil import which
import logging
import sys
from xonsh.platform import ON_WINDOWS
if ON_WINDOWS:
    import mslex as shlex
else:
    import shlex

# All ENV should be set before loading, and this will make code more clear
SUBPROC_FILE   = __xonsh__.env.get('XONTRIB_ONEPATH_SUBPROC_FILE', True) # In windows, file.exe can be easily installed while python-magic is a little difficult
DEBUG          = __xonsh__.env.get('XONTRIB_ONEPATH_DEBUG', True)
ACTIONS        = __xonsh__.env.get('XONTRIB_ONEPATH_ACTIONS', {
                                        '<DIR>': 'cd',
                                        '<XFILE>': '<RUN>',
                                        '.xsh': 'xonsh'
                                    })
SEARCH_IN_PATH = __xonsh__.env.get('XONTRIB_ONEPATH_SEARCH_IN_PATH', True)


def _get_subproc_output(cmds):
    cmds = [str(c) for c in cmds]
    # if not debug and not ON_WINDOWS:
    #     cmds += ['2>', os.devnull]
    result = __xonsh__.subproc_captured_object(cmds)
    result.rtn  # workaround https://github.com/xonsh/xonsh/issues/3394
    return result.output

def mime(path :Path):
    file_type = _get_subproc_output(['file', '--mime-type', '--brief', path]).strip()
    return file_type
    # import magic
    # if SUBPROC_FILE:
    #     file_type = _get_subproc_output(['file', '--mime-type', '--brief', path], debug).strip()
    # else:
    #     try:
    #         file_type = magic.from_file(str(path), mime=True)
    #     except IsADirectoryError:
    #         file_type = 'inode/directory'

def _is_executable(path):
    if not path.is_file():
        return False
    if ON_WINDOWS:
        pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").lower().split(";")
        return path.suffix in pathext
    else:
        return os.access(path, os.X_OK)

def parse_action(file_types :dict, actions :dict = ACTIONS):
    action = None
    for k in actions:
        for name, tp in file_types.items():
            if k == tp:
                action = actions[k]
                logging.debug(f'xontrib-onepath: selected action name={repr(name)}, type={repr(k)}, action={repr(action)}')            
                break
        if action:
            break
    return action

def _onepath(cmd, **kw):
    try:
        args = shlex.split(cmd)
    except:
        logging.debug("shlex.split/mslex.split failed")
        return None
    logging.debug(f"shlex.split/mslex.split success: {args=}")

    if len(args) != 1:
        logging.debug(f"{len(args)=} != 1, exiting")
        return None

    if args[0] in aliases:
        logging.debug("detected in alias, exiting")
        return None
    
    path = Path(args[0]).expanduser()
    logging.debug(f"onepath is {path}")

    if not path.is_absolute() and args[0][0] != '.':
        if SEARCH_IN_PATH and which(args[0]):
            path = Path(which(args[0])).expanduser()
        else:
            return None
    
    path = path.resolve()
    if not path.exists():
        logging.debug(f"{path} no exist! exiting")
        return None

    file_type=mime(path)

    file_types = {
        'full_path': str(path),
        'path_filename': None if path.is_dir() else path.name,
        'path_suffix_key': '*' + path.suffix,
        'file_type_suffix': file_type + path.suffix,
        'file_type': '<DIR>' if file_type == 'inode/directory' else file_type,
        'file_type_group': file_type.split('/')[0] + '/' if '/' in file_type else None,
        'file_or_dir': '<FILE>' if path.is_file() else '<DIR>',
        'xfile': '<XFILE>' if _is_executable(path) else '<NX>',
        'any': '*'
    }
    
    logging.debug(f'xontrib-onepath: types for {path} is {file_types}')

    action = parse_action(file_types)
    logging.debug(f"{action=}")

    if action:
        if action == '<RUN>':
            return f'{shlex.quote(str(path))}\n'
        else:
            return f'{action} {shlex.quote(str(path))}\n'
    else:
        return None


@events.on_transform_command
def onepath(cmd, **kw):
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG if DEBUG else logging.WARNING,
    )

    logging.debug(f"\n{cmd=}")
    result = _onepath(cmd, **kw)
    logging.debug(f"{result=}")
    return result if result is not None else cmd

# When XONTRIB_ONEPATH_SUBPROC_FILE is True, import should not happen to avoid import issues
# Use os.devnull to work in both Linux (/dev/null) and Windows (NUL)
# Windows use `\` for path, shlex.quote could not escape it correctly. As https://docs.python.org/3/library/shlex.html says, "Warning The shlex module is only designed for Unix shells. The quote() function is not guaranteed to be correct on non-POSIX compliant shells or shells from other operating systems such as Windows. Executing commands quoted by this module on such shells can open up the possibility of a command injection vulnerability."
# adding r'' is a little trick and it may broke other commands, may be mslex is a better option
# X_OK is always True whether it's executable
