#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""cylc [admin] check-software [MODULES]

Check for Cylc external software dependencies, including minimum versions.

With no arguments, prints a table of results for all core & optional external
module requirements, grouped by functionality. With module argument(s),
provides an exit status for the collective result of checks on those modules.

Arguments:
    [MODULES]   Modules to include in the software check, which returns a
                zero ('pass') or non-zero ('fail') exit status, where the
                integer is equivalent to the number of modules failing. Run
                the bare check-software command to view the full list of
                valid module arguments (lower-case equivalents accepted).
"""

import os
import re
import sys

from cylc.flow.cylc_subproc import procopen

# Standardised output messages
FOUND_NOVER_MSG = 'FOUND'
MINVER_MET_MSG = 'FOUND & min. version MET'
MINVER_NOTMET_MSG = 'FOUND but min. version NOT MET'
FOUND_UNKNOWNVER_MSG = 'FOUND but could not determine version (?)'
NOTFOUND_MSG = 'NOT FOUND (-)'

"""Specification of cylc core & full-functionality module requirements, the
latter grouped as Python or 'other'. 'opt_spec' item format:
<MODULE>: [<MIN VER OR 'None'>, <FUNC TAG>, <GROUP>, <'OTHER' TUPLE>] with
<'OTHER' TUPLE> = ([<BASE CMD(S)>], <VER OPT>, <REGEX>, <OUTFILE ARG>).
"""
req_py_ver_range = ((3, 7),)
opt_spec = {
    'EmPy': [(3, 3, 4), 'TEMPLATING', 'PY'],
}

# All possible module reqs to accept as arguments, as above or all lower case.
module_args = ['Python'] + list(opt_spec)
upper_case_conv = dict(
    (upper.lower(), upper) for upper in module_args if upper.lower() != upper)

# Package-dep. functionality dict; item format <FUNC TAG>: <FULL DESCRIPTION>
func_tags_and_text = {
    'TEMPLATING': 'configuration templating',
}

# Initialise results dict
opt_result = {}


def output_width(min_width=65, max_width=90):
    """Return a suitable output alignment width given user terminal width."""
    proc = procopen(['stty', 'size'], stdoutpipe=True)
    if proc.wait():
        return int((min_width + max_width) / 2)
    else:
        try:
            return max(min_width, min(max_width,
                                      int(proc.communicate()[0].split()[1])))
        except IndexError:
            return int((min_width + max_width) / 2)


def draw_table_line(single_character):
    sys.stdout.write(single_character * output_width() + '\n')
    return None


def parse_version(version):
    ret = []
    for sub_version in version.split('.'):
        try:
            ret.append(int(sub_version))
        except ValueError:
            ret.append(sub_version)
    return tuple(ret)


def string_ver(version_tuple):
    return '.'.join(str(x) for x in version_tuple)


def shell_align_write(one_delimiter, left_msg, right_msg):
    """Write two messages aligned with the terminal edges.

    Messages are separated by a given delimiter and have a minimum separation
    of two characters.
    """
    gap = output_width() - len(left_msg) - len(right_msg)
    if gap >= 2:
        sys.stdout.write(left_msg + one_delimiter * gap + right_msg + '\n')
        return True
    else:
        return False


def shell_centre_write(prepend_newline, *args):
    """Write one or more lines of text centrally in the terminal."""
    if prepend_newline:
        sys.stdout.write('\n')
    for msg_line in args:
        spacing = int(round(output_width() - len(msg_line)) / 2) * ' '
        sys.stdout.write(spacing + msg_line + spacing + '\n')
    return


def check_py_ver(min_ver, max_ver=None, write=True):
    """Check if a version of Python within a specified range is installed."""
    if max_ver:
        msg = 'Python (%s+, <%s)' % (string_ver(min_ver), string_ver(max_ver))
    else:
        msg = 'Python (%s+)' % string_ver(min_ver)
    version = sys.version_info
    ret = (version >= min_ver and (not max_ver or version < max_ver))
    if write:
        shell_align_write('.', msg, '%s (%s)' % (MINVER_MET_MSG if ret else
                                                 MINVER_NOTMET_MSG,
                                                 string_ver(version)))
    return ret


def check_py_module_ver(module, min_ver, write=True):
    """Check if a minimum version of a Python module is installed."""
    msg = 'Python:%s (%s)' % (module, string_ver(min_ver) + '+' if
                              min_ver is not None else 'any')
    try:
        if module == 'EmPy':
            # we want the 'em' module, but there is more than one out there
            # we want the one that provides 'Interpreter'
            from em import Interpreter  # noqa: F401

            module_version = sys.modules['em'].__version__
        elif module == 'ansimarkup':
            import ansimarkup  # noqa: F401
            import pkg_resources
            module_version = pkg_resources.get_distribution(
                'ansimarkup').version
        elif module == 'protobuf':
            from google import protobuf
            module_version = protobuf.__version__
        else:
            imported_module = __import__(module)
            module_version = imported_module.__version__
    except ImportError:
        res = [NOTFOUND_MSG, False]
    except AttributeError:
        res = [FOUND_UNKNOWNVER_MSG, False]
    else:
        try:
            if min_ver is None:
                res = ['%s (%s)' % (FOUND_NOVER_MSG, module_version), True]
            elif parse_version(module_version) >= min_ver:
                res = ['%s (%s)' % (MINVER_MET_MSG, module_version), True]
            else:
                res = ['%s (%s)' % (MINVER_NOTMET_MSG, module_version), False]
        except AttributeError:
            res = [FOUND_UNKNOWNVER_MSG, False]
    if write:
        shell_align_write('.', msg, res[0])
    return res[1]


def cmd_find_ver(module, min_ver, cmd_base, ver_opt, ver_extr, outfile=1,
                 write=True):
    """Print outcome & return Boolean (True for pass) of local module version
    requirement test using relevant custom command base keyword(s),
    version-checking option(s) & version-extraction regex.
    """
    msg = '%s (%s)' % (module, string_ver(min_ver) + '+' if
                       min_ver is not None else 'any')
    for cmd in cmd_base:
        try_next_cmd = True
        if procopen(['which', cmd], stdin=open(os.devnull),
                    stdoutpipe=True, stderrpipe=True).wait():
            res = [NOTFOUND_MSG, False]
        else:
            try:
                output = procopen(
                    [cmd, ver_opt], stdoutpipe=True,
                    stdin=open(os.devnull),
                    stderrpipe=True).communicate()[outfile - 1].decode()\
                    .strip()
                version = re.search(ver_extr, output).groups()[0]
                try_next_cmd = False
                if min_ver is None:
                    res = ['%s (%s)' % (FOUND_NOVER_MSG, version), True]
                elif parse_version(version) >= min_ver:
                    res = ['%s (%s)' % (MINVER_MET_MSG, version), True]
                else:
                    res = ['%s (%s)' % (MINVER_NOTMET_MSG, version), False]
            except AttributeError:
                res = [FOUND_UNKNOWNVER_MSG, False]
        if not try_next_cmd:
            break
    if write:
        shell_align_write('.', msg, res[0])
    return res[1]


def functionality_print(func):
    """Print outcome of module checks as necessary for some functionality."""
    for module, items in opt_spec.items():
        ver_req, func_dep, tag = items[:3]
        if func_dep == func:
            if tag == 'PY':
                opt_result[module] = check_py_module_ver(module, ver_req)
            elif tag == 'OTHER':
                opt_result[module] = cmd_find_ver(module, ver_req, *items[3])
    return


def individual_status_print(module):
    """Return a pass (0) or fail (1) result for an individual module check."""
    if module == 'Python':
        return int(not check_py_ver(*req_py_ver_range, write=False))
    if module in opt_spec.keys():
        ver_req, _, tag = opt_spec[module][:3]
        if tag == 'PY':
            return int(not check_py_module_ver(module, ver_req, write=False))
        elif tag == 'OTHER':
            other_args = opt_spec[module][3]
            return int(
                not cmd_find_ver(module, ver_req, *other_args, write=False))


def main():
    """Check whether Cylc external software dependencies are satisfied.

    Search local filesystem for external software packages of at least minimum
    version as required for both minimal core and fully-functional Cylc.

    If arguments are supplied, test for those module(s) only and return an exit
    code where zero indicates a collective pass and a non-zero integer
    indicates the number of module arguments that fail or are invalid, else
    check for all dependencies and print results in a table.
    """

    # Check for valid module argument(s); if present exit with relevant code.
    exit_status = 0
    for user_arg in sys.argv[1:]:
        if user_arg in module_args:
            exit_status += individual_status_print(user_arg)
        elif user_arg in upper_case_conv:  # lower-case equivalents
            exit_status += individual_status_print(upper_case_conv[user_arg])
        else:
            sys.stdout.write("No such module '%s' in the software "
                             "dependencies.\n" % user_arg)
            exit_status += 1
        if user_arg == sys.argv[-1]:  # give exit code after last user argument
            sys.exit(exit_status)

    # No arguments: table. Introductory message and individual results header.
    sys.stdout.write('Checking your software...\n\nIndividual results:\n')
    draw_table_line('=')
    shell_align_write(' ', 'Package (version requirements)',
                      'Outcome (version found)')
    draw_table_line('=')

    # Individual results section in mock-table format.
    shell_centre_write(False, '*REQUIRED SOFTWARE*')
    req_result = (
        check_py_ver(*req_py_ver_range)
        and check_py_module_ver('zmq', None)
        and check_py_module_ver('graphene', None)
        and check_py_module_ver('colorama', None)
        and check_py_module_ver('ansimarkup', None)
        and check_py_module_ver('protobuf', (3, 7, 0))
    )
    for tag, text in func_tags_and_text.items():
        shell_centre_write(True, '*OPTIONAL SOFTWARE for the ' + text + '*')
        functionality_print(tag)
    draw_table_line('=')

    # Final summary print for clear pass/fail final outcome & exit.
    sys.stdout.write('\nSummary:')
    shell_centre_write(True, '*' * 28,
                       'Core requirements: %s' % (
                           'ok' if req_result else 'not ok'),
                       'Full-functionality: %s' % (
                           'ok' if all(opt_result.values()) else 'not ok'),
                       '*' * 28)
    sys.exit()


if __name__ == '__main__':
    if 'help' in sys.argv or '--help' in sys.argv:
        print(__doc__)
    else:
        main()
