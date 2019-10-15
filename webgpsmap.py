__author__ = 'https://github.com/xenDE/pwnagotchi-plugin-webgpsmap'
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


OPTIONS = dict()
AGENT = None


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
    if not AGENT:
        response.send_response(500)
        return

    try:
        res = get_html()
    except json.JSONDecodeError as js_e:
        response.send_response(500)
        return
    except OSError as os_e:
        response.send_response(500)
        return

    response.send_response(200)
    response.send_header('Content-type', 'text/html')
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
    NETPOS = 1
    GEO = 2

    def __init__(self, path):
        self._file = path
        try:
            with open(path, 'r') as json_file:
                self._json = json.load(json_file)
        except json.JSONDecodeError as js_e:
            raise js_e

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
        if self._file.endswith('.net-pos.json'):
            return PositionFile.NETPOS
        if self._file.endswith('.geo.json'):
            return PositionFile.GEO
        return None

    def lat(self):
        try:
            if self.type() == PositionFile.GPS:
                return self._json['Latitude']
            if self.type() == PositionFile.NETPOS or self.type() == PositionFile.GEO:
                return self._json['location']['lat']
        except KeyError:
            pass
        return None

    def lng(self):
        try:
            if self.type() == PositionFile.GPS:
                return self._json['Longitude']
            if self.type() == PositionFile.NETPOS or self.type() == PositionFile.GEO:
                return self._json['location']['lng']
        except KeyError:
            pass
        return None

    def accuracy(self):
        if self.type() == PositionFile.GPS:
            return 50.0
        if self.type() == PositionFile.NETPOS or self.type() == PositionFile.GEO:
            try:
                return self._json['accuracy']
            except KeyError:
                pass
        return None

def get_gps_data():
    """
    Parses the gps-data from disk
    """
    config = AGENT.config()
    handshake_dir = config['bettercap']['handshakes']
    gps_data = dict()
    all_files = os.listdir(handshake_dir)
    all_geo_or_gps_files = [os.path.join(handshake_dir, filename)
                            for filename in all_files
                            if filename.endswith('.json')
                            ]
    logging.info("webgpsmap: Found %d .json files. Fetching positions ...",
                 len(all_geo_or_gps_files))
    for pos_file in all_geo_or_gps_files:
        try:
            pos = PositionFile(pos_file)
            ssid, mac = os.path.basename(pos_file).split('.', 2)[0].split('_', 1)

            gps_data[ssid] = {
                'ssid': ssid,
                'mac': mac,
                'type': 'gps' if pos.type() == PositionFile.GPS else 'geo',
                'lng': pos.lng(),
                'lat': pos.lat(),
                'acc': pos.accuracy(),
                }
        except json.JSONDecodeError as js_e:
            raise js_e
        except OSError as os_e:
            raise os_e
    logging.debug("plugin webgpsmap loaded %d positions: ", len(gps_data))

    return gps_data


def get_html():
    """
    Returns the html page
    """
    gps_data = get_gps_data()
    returnstr = """
<html>
<head>
  <meta http-equiv="Content-Type" content="text/xml; charset=utf-8" />
  <title>WEB GPS MAP</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/openlayers/2.11/lib/OpenLayers.js"></script>
  <style type="text/css">
    html, body, #mapdiv {{ width:100%; height:100%; margin:0; }}
  </style>
</head>
<body>
  <div id="mapdiv"></div>
  <script>
    positions = {gps_data};
    var map = new OpenLayers.Map("mapdiv");
    var popup;

    map.addLayer(new OpenLayers.Layer.OSM());

    var markers = new OpenLayers.Layer.Markers( "APs" );
    map.addLayer(markers);

    console.log( "have " + Object.keys(positions).length + " positions to show");
    Object.keys(positions).forEach(function(ssid) {{
//      console.log(ssid, positions[ssid]);
      var lonLat = new OpenLayers.LonLat( positions[ssid].lng ,positions[ssid].lat )
          .transform(
            new OpenLayers.Projection("EPSG:4326"), // transform from WGS 1984
            map.getProjectionObject() // to Spherical Mercator Projection
          );
      new_marker = new OpenLayers.Marker(lonLat);

      new_marker.events.register('mouseover', new_marker, function(evt) {{
        popup = new OpenLayers.Popup.FramedCloud("Popup",
            lonLat,
            null,
            '<div>' + ssid + '(' + 'mac: ' + positions[ssid].mac + 'src: ' + positions[ssid].type + ')' + '</div>',
            null,
            false);
        map.addPopup(popup);
      }});
      //here add mouseout event
      new_marker.events.register('mouseout', new_marker, function(evt) {{popup.hide();}});

      markers.addMarker(new_marker);
    }});

    var newBound = markers.getDataExtent();
    map.zoomToExtent(newBound);
  </script>
</body></html>
"""
    return returnstr.format(gps_data=json.dumps(gps_data))
