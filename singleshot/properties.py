"""This module has slowly been accumulating various utility functions."""

__all__ = ['AutoPropertyMeta',
           'ViewMeta',
           'trace',
           'demand_property',
           'config_property',
           'delegate_property',
           'PackedRecord',
           'parse_iso8601',
           'parse_exif_datetime',
           'dtfromtimestamp']


import sys
from shotlib.util import demand_property
from shotlib.properties import AutoPropertyMeta, ViewMeta, wrap_printexc, trace, config_property, delegate_property, PackedRecord
import logging
from datetime import tzinfo, datetime, timedelta
import time as _time

import pytz
from shotlib.dates import parse_iso8601, parse_exif_datetime

def dtfromtimestamp(t):
    return datetime.fromtimestamp(t, tz=pytz.utc)

# what a hack
Local = pytz.timezone('US/Pacific')
