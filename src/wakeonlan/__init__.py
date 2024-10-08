# Copyright (c) 2018, Eugene Gershnik
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE.txt file or at
# https://opensource.org/licenses/BSD-3-Clause

"""wakeonlan package"""

from .wakeonlan import VERSION as __version__, wake, save_name, get_name_record, get_names, delete_name

__all__ = [
    'wake',
    'save_name',
    'get_name_record',
    'get_names',
    'delete_name'
]
