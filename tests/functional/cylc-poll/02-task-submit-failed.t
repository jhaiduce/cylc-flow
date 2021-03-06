#!/usr/bin/env bash
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
#-------------------------------------------------------------------------------
# Test that polling a submit-failed task sets the task state correctly
. "$(dirname "$0")/test_header"
skip_darwin 'atrun hard to configure on Mac OS'
set_test_number 2

create_test_global_config "" "
[platforms]
[[crocodile]]
  hosts = localhost
  install target = localhost
  batch system = at
  batch submit command template = at noon tomorrow
"

reftest
exit
