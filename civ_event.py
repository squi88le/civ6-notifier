"""
Civ6 event parser and notification forwarder
"""
# pylint: disable=C0301
# pylint: disable=R0903
# pylint: disable=R0201

import json
import re
import os
import time

from os import path
from datetime import datetime
from enum import Enum
from collections import namedtuple

import requests

class EventType(Enum):
    """ Event types """

    UNMAPPED = 0    # Events we don't care about
    COMMIT = 1      # Game has been committed


class Config():
    """ Simple config handler """

    def __init__(self):
        self._config = None

    def _load(self):
        loc = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(loc, 'config.json')) as cfg_f:
            self._config = json.load(cfg_f)

    def __getitem__(self, k):
        if self._config is None:
            self._load()
        return self._config.get(k)


CFG = Config()


class Handler:
    """ Base class for event handlers """

    def __init__(self):
        self._handlers = []

    def handle(self, line):
        """ Execute handlers """
        for hdlr in self._handlers:
            if hdlr(line):
                return True
        return False

    def add_handlers(self, hdlrs):
        """ Add a handler """
        self._handlers.extend(hdlrs)


class MatchTable(Handler):
    """ Handler for game list entries """

    def __init__(self):
        super().__init__()
        self._matches = {}
        self.add_handlers([
            self._handle_gamelist
        ])
        expr = {
            'game': r'^\[(.*)\]\sCloud Game, LobbyID\((\d+)\), MatchID\((\d+)\), JoinCode\((.*)\), Name\((.*)\)'
        }
        self._re = {k: re.compile(v) for k, v in expr.items()}

    def _handle_gamelist(self, line):
        obj = self._re['game'].match(line)
        if obj is not None:
            timestamp, lobby, match, joincode, name = obj.groups()
            self._matches[match] = (timestamp, name, lobby, joincode)
            return True
        return False

    def __getitem__(self, k):
        return self._matches.get(k)


Session = namedtuple('Session', ['timestamp', 'match'])
class EventList(Handler):
    """ Handler for game events """

    def __init__(self):
        super().__init__()
        self._events = []
        self._session = None
        self.add_handlers([
            self._handle_join,
            self._handle_srlze
        ])
        expr = {
            'join': r'^\[(.*)\]\sReceived\smatch\sdata\sfor\s(?:joined|hosted)\scloud match\.\smatchID\s(\d+)',
            'save': r'^\[(.*)\]\sSerialization\sRequest\.\sType\:\s1,\sLocation\sType:\s2,\sDevice:\s\d+,\sOptions\s00000200'
        }
        self._re = {k: re.compile(v) for k, v in expr.items()}

    def _handle_join(self, line):
        obj = self._re['join'].match(line)
        if obj is not None:
            timestamp, match = obj.groups()
            if self._session is None or self._session.match != match:
                self._session = Session(timestamp, match)
                return True
        return False

    def _handle_srlze(self, line):
        obj = self._re['save'].match(line)
        if obj is not None and self._session is not None:
            timestamp, = obj.groups()
            sts, match = self._session
            self._events.append((timestamp, sts, match, EventType.COMMIT))
            return True
        return False

    def __getitem__(self, i):
        return self._events[i]

    def __len__(self):
        return len(self._events)


class Parser:
    """ Log parser """

    def __init__(self, state):
        self._matches = MatchTable()
        self._events = EventList()
        self._state = state
        self._handlers = [
            self._matches.handle,
            self._events.handle
        ]

    def _wait_on_log(self, wait):
        for _ in range(wait):
            if path.exists(CFG['log_file']):
                return True
            time.sleep(1)
        return False

    def parse_log(self):
        """ Parse the log """

        # wait for log file to exist
        if not self._wait_on_log(30):
            return

        # single pass through all lines in log
        with open(CFG['log_file']) as log_f:
            for line in log_f:
                for hdlr in self._handlers:
                    if hdlr(line):
                        break

        # dispatch 'new' events by comparison with state
        for i in range(len(self._events)):
            ets, sts, match, typ = self._events[i]
            timestamp = datetime.strptime(ets, '%Y-%m-%d %H:%M:%S').timestamp()
            if timestamp > self._state['last_update']:
                self._dispatch_event((ets, sts, match, typ))
                self._state['last_update'] = timestamp

    def _dispatch_event(self, event):
        # take action based on event type
        ets, sts, match, typ = event
        if typ == EventType.COMMIT:
            _, name, lobby, _ = self._matches[match]
            self._notify_all({
                "user":     CFG['user'],
                "name":     name,
                "lobby":    lobby,
                "event_ts": ets,
                "join_ts":  sts,
                "match":    match
            })
        elif typ == EventType.UNMAPPED:
            pass

    def _notify_all(self, event):
        notified = False
        for fil in CFG['webhooks']["filters"]:
            if event['name'] in fil['matches']:
                notified = self._notify(fil['webhook'], 
                                        fil['message'].format(**event))

        if not notified:
            self._notify(CFG['webhooks']['default'],
                         CFG['webhooks']['message'].format(**event))

    def _notify(self, webhook, msg):
        res = requests.post(webhook,
                            headers={'Content-Type': 'application/json'},
                            json={'content': msg})
        return res.status_code == 204


def main():
    """ Entry point """

    state = None
    here = os.path.dirname(os.path.realpath(__file__))
    sfile = os.path.join(here, 'state.json')

    # load previous state or create if first run
    if not path.exists(sfile):
        state = {'last_update': 0}
    else:
        with open(sfile) as state_f:
            state = json.load(state_f)

    # do main parsing with state
    Parser(state).parse_log()

    # save new state
    with open(sfile, 'w') as state_f:
        json.dump(state, state_f)

if __name__ == "__main__":
    main()
