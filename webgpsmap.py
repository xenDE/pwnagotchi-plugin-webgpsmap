__author__ = 'https://github.com/xenDE/pwnagotchi-plugin-webgpsmap and https://github.com/dadav'
__version__ = '1.0.0-alpha'
__name__ = 'webgpsmap'
__license__ = 'GPL3'
__description__ = 'a plugin for pwnagotchi that shows a openstreetmap with positions of ap-handshakes in the webbrowser'
__help__ = """
-install: copy "webgpsmap.py" to your configured "custom_plugins" directory and add+edit webgpsmap config to /etc/pnagotchi/config.yml:
⋅⋅⋅    custom_plugins: /usr/local/pwnagotchi/plugins
⋅⋅⋅    plugins:
⋅⋅⋅      webgpsmap:
⋅⋅⋅        enabled: true
⋅⋅⋅        dir-handshakes: /special/dir/for/handshake/data/
"""

import logging
import os
import json
import re
from functools import lru_cache


OPTIONS = dict()
AGENT = None
ALREADY_SENT = list()
SKIP = list()


def on_loaded():
    """
    Plugin got loaded
    """
    logging.info("webgpsmap plugin loaded")

def on_ready(agent):
    """
    Save the agent obj
    """
    global AGENT
    AGENT = agent


def on_internet_available(agent):
    """
    Save the agent obj
    """
    global AGENT
    AGENT = agent

def on_webhook(response, path):
    """
    Returns a map with gps data
    """
    global ALREADY_SENT

    if not AGENT:
        response.send_response(500)
        response.send_header('Content-type', 'text/html')
        response.end_headers()
        try:
            response.wfile.write(bytes('''<html>
                <head>
                <meta charset="utf-8">
                <style>body{font-size:1000%;}</style>
                </head>
                <body>Not ready yet</body>
                </html>''', "utf-8"))
        except Exception as ex:
            logging.error(ex)
        return

    if path == '/' or not path:
        # returns the html template
        ALREADY_SENT = list()
        res = get_html()
        response.send_response(200)
        response.send_header('Content-type', 'text/html')
    elif path.startswith('/all'):
        # returns all positions
        ALREADY_SENT = list()
        res = json.dumps(load_gps_from_dir(AGENT.config()['bettercap']['handshakes']))
        response.send_response(200)
        response.send_header('Content-type', 'application/json')
    elif path.startswith('/newest'):
        # returns all positions newer then timestamp
        res = json.dumps(load_gps_from_dir(AGENT.config()['bettercap']['handshakes']), newest_only=True)
        response.send_response(200)
        response.send_header('Content-type', 'application/json')
    else:
        res = '''<html>
        <head>
        <meta charset="utf-8">
        <style>body{font-size:1000%;}</style>
        </head>
        <body>4😋4</body>
        </html>'''
        response.send_response(404)

    response.end_headers()

    try:
        response.wfile.write(bytes(res, "utf-8"))
    except Exception as ex:
        logging.error(ex)


class PositionFile:
    """
    Wraps gps / net-pos files
    """
    GPS = 0
    GEO = 1

    def __init__(self, path):
        self._file = path
        self._filename = os.path.basename(path)

        try:
            with open(path, 'r') as json_file:
                self._json = json.load(json_file)
        except json.JSONDecodeError as js_e:
            raise js_e

    def mac(self):
        """
        Returns the mac from filename
        """
        parsed_mac = re.search(r'.*_?([a-zA-Z0-9]{12})\.(?:gps|geo)\.json', self._filename)
        if parsed_mac:
            mac = parsed_mac.groups()[0]
            mac_it = iter(mac)
            mac = ':'.join([a + b for a, b in zip(mac_it, mac_it)])
            return mac
        return None

    def ssid(self):
        """
        Returns the ssid from filename
        """
        parsed_ssid = re.search(r'(.+)_[a-zA-Z0-9]{12}\.(?:gps|geo)\.json', self._filename)
        if parsed_ssid:
            return parsed_ssid.groups()[0]
        return None


    def json(self):
        """
        returns the parsed json
        """
        return self._json

    def type(self):
        """
        returns the type of the file
        """
        if self._file.endswith('.gps.json'):
            return PositionFile.GPS
        if self._file.endswith('.geo.json'):
            return PositionFile.GEO
        return None

    def lat(self):
        try:
            if self.type() == PositionFile.GPS:
                lat = self._json['Latitude']
            if self.type() == PositionFile.GEO:
                lat = self._json['location']['lat']
            if lat > 0:
                return lat
            raise ValueError("Lat is 0")
        except KeyError:
            pass
        return None

    def lng(self):
        try:
            if self.type() == PositionFile.GPS:
                lng = self._json['Longitude']
            if self.type() == PositionFile.GEO:
                lng = self._json['location']['lng']
            if lng > 0:
                return lng
            raise ValueError("Lng is 0")
        except KeyError:
            pass
        return None

    def accuracy(self):
        if self.type() == PositionFile.GPS:
            return 50.0
        if self.type() == PositionFile.GEO:
            try:
                return self._json['accuracy']
            except KeyError:
                pass
        return None

# cache 1024 items
@lru_cache(maxsize=1024, typed=False)
def _get_pos_from_file(path):
    return PositionFile(path)


def load_gps_from_dir(gpsdir, newest_only=False):
    """
    Parses the gps-data from disk
    """
    global ALREADY_SENT
    global SKIP

    handshake_dir = gpsdir
    gps_data = dict()
    all_files = os.listdir(handshake_dir)
    all_geo_or_gps_files = [os.path.join(handshake_dir, filename)
                            for filename in all_files
                            if filename.endswith('.json')
                            ]

    all_geo_or_gps_files = set(all_geo_or_gps_files) - set(SKIP)

    if newest_only:
        all_geo_or_gps_files = set(all_geo_or_gps_files) - set(ALREADY_SENT)

    logging.info("webgpsmap: Found %d .json files. Fetching positions ...",
                 len(all_geo_or_gps_files))

    for pos_file in all_geo_or_gps_files:
        try:
            pos = _get_pos_from_file(pos_file)
            if not pos.type() == PositionFile.GPS and not pos.type() == PositionFile.GEO:
                continue

            ssid, mac = pos.ssid(), pos.mac()
            ssid = "unknown" if not ssid else ssid
            # invalid mac is strange and should abort; ssid is ok
            if not mac:
                raise ValueError('Mac cant be parsed from filename')

            gps_data[ssid+"_"+mac] = {
                'ssid': ssid,
                'mac': mac,
                'type': 'gps' if pos.type() == PositionFile.GPS else 'geo',
                'lng': pos.lng(),
                'lat': pos.lat(),
                'acc': pos.accuracy(),
                }
            ALREADY_SENT += pos_file
        except json.JSONDecodeError as js_e:
            SKIP += pos_file
            logging.error(js_e)
            continue
        except ValueError as v_e:
            SKIP += pos_file
            logging.error(v_e)
            continue
        except OSError as os_e:
            SKIP += pos_file
            logging.error(os_e)
            continue
    logging.debug("plugin webgpsmap loaded %d positions: ", len(gps_data))

    return gps_data


def get_html():
    """
    Returns the html page
    """
    html_data = open(os.path.dirname(os.path.realpath(__file__))+"/"+"webgpsmap.html", "r").read()
    return html_data
