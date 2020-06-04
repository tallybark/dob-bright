# This file exists within 'dob-bright':
#
#   https://github.com/hotoffthehamster/dob-bright
#
# Copyright © 2018-2020 Landon Bouma. All rights reserved.
#
# This program is free software:  you can redistribute it  and/or  modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3  of the License,  or  (at your option)  any later version  (GPLv3+).
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY;  without even the implied warranty of MERCHANTABILITY or  FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU  General  Public  License  for  more  details.
#
# If you lost the GNU General Public License that ships with this software
# repository (read the 'LICENSE' file), see <http://www.gnu.org/licenses/>.

import click_hotoffthehamster as click
import lazy_import

from dob_bright.termio import attr, click_echo

# (lb): I know, I know, 3 table libraries! I couldn't find one I liked the
# best, so now they're all included, and the user can choose their fave.
# Profiling: load times:
#  ~ 0.004 secs.  / from tabulate import tabulate
#  ~ 0.015 secs.  / from texttable import Texttable
#  ~ 0.020 secs.  / from humanfriendly.tables import format_pretty_table
tabulate = lazy_import.lazy_module('tabulate')
texttable = lazy_import.lazy_module('texttable')
format_pretty_table = lazy_import.lazy_callable(
    'humanfriendly.tables.format_pretty_table'
)

__all__ = (
    'generate_table',
)


def generate_table(
    rows,
    headers,
    table_type='friendly',
    truncate=False,
    trunccol=None,
):
    """Generates an ASCII table using the generator specified by table_type."""
    # Add some flair to the header labels.
    plain_headers = headers
    color_headers = _generate_table_color_headers(plain_headers)
    # Determine the max_width of the elastic cell; or use 0, if not truncating.
    max_width = _generate_table_max_width(rows, headers, table_type, truncate, trunccol)
    # Truncate long values in the trunccol column, if requested.
    trows = _generate_table_truncate_cell_values(rows, trunccol, max_width)
    _generate_table_display(trows, plain_headers, color_headers, table_type)


def _generate_table_color_headers(plain_headers):
    # Colorful headers.
    color_headers = []
    for header in plain_headers:
        color_headers.append(
            '{}{}{}'.format(attr('underlined'), header, attr('reset'),),
        )
    return color_headers


def _generate_table_max_width(rows, headers, table_type, truncate, trunccol):
    if not truncate or not rows:
        return -1
    num_cols = len(rows[0])
    column_width_used = _generate_table_width_content(rows, num_cols, trunccol)
    border_width_used = _generate_table_width_border(rows, num_cols, table_type)

    # Determine the width available for the elastic column.
    term_width, _term_height = click.get_terminal_size()
    ellipsis_width = len('...')
    max_width = term_width - (border_width_used + column_width_used + ellipsis_width)
    # (lb): We at least have the width of the header string!
    min_avail = len(headers[trunccol]) if trunccol is not None else 0
    min_avail -= ellipsis_width
    max_width = max(0, min_avail, max_width)

    return max_width


def _generate_table_width_content(rows, num_cols, trunccol):
    # Calculate max column widths.
    max_widths = [0] * num_cols
    for row in rows:
        for idx, col in enumerate(row):
            max_widths[idx] = max(max_widths[idx], len(str(col)))
    column_width_used = 0
    for idx, width in enumerate(max_widths):
        if idx == trunccol:
            continue
        column_width_used += width
    return column_width_used


def _generate_table_width_border(rows, num_cols, table_type):
    n_inner_borders = num_cols - 1
    # FIXME/2018-05-11 22:09: (lb): This looks nice for 2 columns. Not sure on others.
    border_width_used = (
        len('│ ') + (n_inner_borders * len(' │   ')) + len(' │')
    )
    # (lb): Does this computation work for all formatters and table styles?
    #   tabulate: seems to be exact (table abuts right edge)
    #   texttable: 2 off (but only if terminal narrower than default table width)
    #   friendly: also 2 off
    # ... at least for the currently chosen table border designs.
    if table_type in ('texttable', 'friendly'):
        # MAGIC_NUMBER: Nudge these formatters' widths inward a titch.
        border_width_used -= 2
    # MAGIC_NUMBER: (lb): I like a 1 character column gutter.
    border_width_used += 1
    return border_width_used


def _generate_table_truncate_cell_values(rows, trunccol, max_width):
    trows = []
    for row in rows:
        trow = list(row)
        trows.append(trow)
        if trunccol is None:
            continue
        truncval = trow[trunccol] or ''
        if (max_width >= 0) and (len(truncval) >= max_width):
            trow[trunccol] = truncval[:max_width] + '...'
    return trows


def _generate_table_display(rows, plain_headers, color_headers, table_type):
    """Generates and display a table in for format specified.

    NOTE: 'texttable' is the only library that wraps long column text
    so that it aligns nicely in the terminal, hence it's the default.
    """
    def __generate_table_display():
        if table_type == 'texttable':
            __generate_table_texttable()
        elif table_type == 'journal':
            __generate_table_texttable(plain=True)
        elif table_type == 'friendly' or not table_type:
            __generate_table_friendly()
        else:
            # table_type == 'tabulate' or table_type is tabulate.tablefmt.
            __generate_table_tabulate(table_type)

    def __generate_table_tabulate(table_type):
        tablefmt = "fancy_grid" if table_type == 'tabulate' else table_type
        tabulation = __generate_table_tabulate_tablefmt(tablefmt)
        click_echo(tabulation)

    def __generate_table_tabulate_tablefmt(tablefmt):
        try:
            return tabulate.tabulate(
                rows, headers=color_headers, tablefmt=tablefmt,
            )
        except Exception as err:
            raise ValueError(
                'Unknown table_type: ‘{}’ ({})'.format(table_type, str(err))
            )

    def __generate_table_texttable(plain=False):
        # PROS: Texttable wraps long lines by **default**!
        #       And within the same column!
        #         So you don't need to --truncate.
        #       It even defaults to a nice, narrow, 80-character wide table.
        #       You can set it wider, e.g., Texttable(max_width=term_width),
        #       but the narrow look is sleek, and easy to read.
        # CONS: Texttable counts control characters.
        #       If you add color to your headers, their columns will not
        #       line up with the content rows! (lb): "A deal breaker!"
        ttable = texttable.Texttable()
        if plain:
            ttable.set_deco(0)
        # Right-align the first column; left-align the rest.
        cols_align = ['r']
        for idx in range(1, len(plain_headers)):
            cols_align.append('l')
        ttable.set_cols_align(cols_align)
        if plain:
            ttable.set_header_align(cols_align)
        #
        term_width, _term_height = click.get_terminal_size()
        # We could be deliberate about each column's width, e.g.,
        #   ttable.set_cols_width([a, b, c, d])
        # but the library does an excellent job on its own.
        ttable.set_max_width(term_width)
        #
        if not plain:
            rows.insert(0, plain_headers)
        ttable.add_rows(rows)
        #
        textable = ttable.draw()
        click_echo(textable)

    def __generate_table_friendly():
        # Haha, humanfriendly colors the header text green by default.
        friendly = format_pretty_table(rows, color_headers)
        click_echo(friendly)

    __generate_table_display()

