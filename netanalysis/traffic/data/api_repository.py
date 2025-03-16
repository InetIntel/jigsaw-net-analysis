#!/usr/bin/python
#
# Copyright 2019 Jigsaw Operations LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Library to access Google's traffic data from its Transparency Report
"""
import datetime
import json
import ssl
import time
from urllib.parse import urlencode, quote

import urllib3

import certifi
import pandas as pd

from netanalysis.traffic.data import model


def _to_timestamp(time_point: datetime.datetime):
    return time.mktime(time_point.timetuple())


_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class ApiTrafficRepository(model.TrafficRepository):
    """TrafficRepository that reads the traffic data from Google's Transparency Report."""

    def __init__(self):
        super().__init__()
        self.httppool = urllib3.PoolManager()

    def _query_api(self, endpoint, params=None):
        query_url = "https://transparencyreport.google.com/transparencyreport/api/v3/traffic/" + \
            quote(endpoint)

        headers = {
            "User-Agent": "Jigsaw-Code/netanalysis",
        }

        if params:
            query_url = query_url + "?" + urlencode(params)
        try:
            response = self.httppool.request('GET', query_url, headers=headers)
            return json.loads(response.data[6:].decode("utf8"))
        except Exception as error:
            raise Exception("Failed to query url %s" % query_url, error)

    def list_regions(self):
        response_proto = self._query_api("regionlist")
        return sorted([e[0] for e in response_proto[0][1]])

    def get_traffic(self, region_code: str, product_id: model.ProductId,
                    start: datetime.datetime = None, end: datetime.datetime = None):
        DEFAULT_INTERVAL_DAYS = 2 * 365
        POINTS_PER_DAY = 48
        if not end:
            end = datetime.datetime.now()
        if not start:
            start = end - datetime.timedelta(days=DEFAULT_INTERVAL_DAYS)
        number_of_days = (end - start).days
        total_points = int(number_of_days * POINTS_PER_DAY)
        entries = []
        params = [
            ("start", int(_to_timestamp(start) * 1000)),
            ("end", int(_to_timestamp(end) * 1000)),
            ("width", total_points),
            ("product", product_id.value),
            ("region", region_code)]
        response_proto = self._query_api("fraction", params)
        entry_list_proto = response_proto[0][1]
        if entry_list_proto is None:
            return pd.Series(dtype="object")
        for entry_proto in entry_list_proto:
            timestamp = datetime.datetime.utcfromtimestamp(
                entry_proto[0] / 1000)
            value = entry_proto[1][0][1]
            entries.append((timestamp, value / POINTS_PER_DAY / 2))
        dates, traffic = zip(*entries)
        return pd.Series(traffic, index=dates)
