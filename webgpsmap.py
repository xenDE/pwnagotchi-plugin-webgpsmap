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
            pos_file_basename = os.path.basename(pos_file)
            if '_' not in pos_file_basename:
                pos_file_basename = "unknown_"+pos_file_basename
            ssid, mac = pos_file_basename.split('.', 2)[0].split('_', 1)
            gps_data[ssid+"_"+mac] = {
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
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.5.1/dist/leaflet.css"
  integrity="sha512-xwE/Az9zrjBIphAcBb3F6JVqxf46+CDLwfLMHloNu6KEQCAWi6HcDUbeOfBIptF7tcCzusKFjFw2yuvEpDL9wQ=="
  crossorigin=""/>
  <script src="https://unpkg.com/leaflet@1.5.1/dist/leaflet.js"
  integrity="sha512-GffPMF3RvMeYyc1LWMHtK8EbPv0iNZ8/oTtHPx9/cc2ILxQ+u905qIwdpULaqDkyBKgOaB57QTMg7ztg8Jm2Og=="
  crossorigin=""></script>

  <style type="text/css">
    html, body, #mapdiv {{   height: 100%; width: 100%; margin:0; }}
    .pwnAPPin path {{
      fill: #ce7575;
    }}
    .pwnAPPin .ring_outer {{
      animation: opacityPulse 2s cubic-bezier(1, 0.14, 1, 1);
      animation-iteration-count: infinite;
      opacity: .5;
    }}
    .pwnAPPin .ring_inner {{
      animation: opacityPulse 2s cubic-bezier(0.4, 0.74, 0.56, 0.82);
      animation-iteration-count: infinite;
      opacity: .8;
    }}
    @keyframes opacityPulse {{
      0% {{
        opacity: 0.1;
      }}
      50% {{
        opacity: 1.0;
      }}
      100% {{
        opacity: 0.1;
      }}
    }}
    @keyframes bounceInDown {{
      from, 60%, 75%, 90%, to {{
        animation-timing-function: cubic-bezier(0.215, 0.61, 0.355, 1);
      }}
      0% {{
        opacity: 0;
        transform: translate3d(0, -3000px, 0);
      }}
      60% {{
        opacity: 1;
        transform: translate3d(0, 5px, 0);
      }}
      75% {{
        transform: translate3d(0, -3px, 0);
      }}
      90% {{
        transform: translate3d(0, 5px, 0);
      }}
      to {{
        transform: none;
      }}
    }}
    .bounceInDown {{
      animation-name: bounceInDown;
      animation-duration: 2s;
      animation-fill-mode: both;
    }}
  </style>
</head>
<body>
  <div id="mapdiv"></div>
  <script>
    positions = {gps_data};

    // select your theme from https://leaflet-extras.github.io/leaflet-providers/preview/
    var Esri_WorldImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    }});
    // var OpenStreetMap_Mapnik = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      //   maxZoom: 19,
    //   opacity:0.5,
      //   attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    // }});
    var CartoDB_DarkMatter = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      opacity:0.8,
      maxZoom: 19
    }});
    // var Thunderforest_SpinalMap = L.tileLayer('https://{{s}}.tile.thunderforest.com/spinal-map/{{z}}/{{x}}/{{y}}.png?apikey={{apikey}}', {{
    //   attribution: '&copy; <a href="http://www.thunderforest.com/">Thunderforest</a>, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    //   apikey: '<your apikey>',
    //   maxZoom: 22
    // }});
    var mymap = L.map('mapdiv');
    Esri_WorldImagery.addTo(mymap);
    CartoDB_DarkMatter.addTo(mymap);


    var svg = '<?xml version="1.0" encoding="UTF-8"?><svg class="pwnAPPin" width="80px" height="60px" viewBox="0 0 44 28" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><title>AP</title><desc>Found by pwnagotchi.</desc><defs><linearGradient x1="50%" y1="0%" x2="50%" y2="100%" id="linearGradient-1"><stop stop-color="#FFFFFF" offset="0%"></stop><stop stop-color="#000000" offset="100%"></stop></linearGradient></defs><g id="Page-1" stroke="none" stroke-width="1" fill="none" fill-rule="evenodd"><g id="marker"><path class="ring_outer" d="M28.6,8 C34.7,9.4 39,12.4 39,16 C39,20.7 31.3,24.6 21.7,24.6 C12.1,24.6 4.3,20.7 4.3,16 C4.3,12.5 8.5,9.5 14.6,8.1 C15.3,8 14.2,6.6 13.3,6.8 C5.5,8.4 0,12.2 0,16.7 C0,22.7 9.7,27.4 21.7,27.4 C33.7,27.4 43.3,22.6 43.3,16.7 C43.3,12.1 37.6,8.3 29.6,6.7 C28.8,6.5 27.8,7.9 28.6,8.1 L28.6,8 Z" id="Shape" fill="#878787" fill-rule="nonzero"></path><path class="ring_inner" d="M28.1427313,11.0811939 C30.4951542,11.9119726 32.0242291,13.2174821 32.0242291,14.6416742 C32.0242291,17.2526931 27.6722467,19.2702986 22.261674,19.2702986 C16.8511013,19.2702986 12.4991189,17.2526931 12.4991189,14.7603569 C12.4991189,13.5735301 13.4400881,12.505386 15.0867841,11.6746073 C15.792511,11.3185592 14.7339207,9.30095371 13.9105727,9.77568442 C10.6171806,10.9625112 8.5,12.9801167 8.5,15.2350876 C8.5,19.0329333 14.4986784,22.0000002 21.9088106,22.0000002 C29.2013216,22.0000002 35.2,19.0329333 35.2,15.2350876 C35.2,12.861434 32.7299559,10.6064632 28.8484581,9.30095371 C28.0251101,9.18227103 27.4370044,10.8438285 28.0251101,11.0811939 L28.1427313,11.0811939 Z" id="Shape" fill="#5F5F5F" fill-rule="nonzero"></path><g id="ap" transform="translate(13.000000, 0.000000)"><rect id="apfront" fill="#000000" x="0" y="14" width="18" height="4"></rect><polygon id="apbody" fill="url(#linearGradient-1)" points="3.83034404 10 14.169656 10 18 14 0 14"></polygon><circle class="ring_outer" id="led1" fill="#931F1F" cx="3" cy="16" r="1"></circle><circle class="ring_inner" id="led2" fill="#931F1F" cx="7" cy="16" r="1"></circle><circle class="ring_outer" id="led3" fill="#931F1F" cx="11" cy="16" r="1"></circle><circle class="ring_inner" id="led4" fill="#931F1F" cx="15" cy="16" r="1"></circle><polygon id="antenna2" fill="#000000" points="8.8173082 0 9.1826918 0 9.5 11 8.5 11"></polygon><polygon id="antenna3" fill="#000000" transform="translate(15.000000, 5.500000) rotate(15.000000) translate(-15.000000, -5.500000) " points="14.8173082 0 15.1826918 0 15.5 11 14.5 11"></polygon><polygon id="antenna1" fill="#000000" transform="translate(3.000000, 5.500000) rotate(-15.000000) translate(-3.000000, -5.500000) " points="2.8173082 0 3.1826918 0 3.5 11 2.5 11"></polygon></g></g></g></svg>';

      var myIcon = L.divIcon({{
      className: "leaflet-data-marker",
        html: svg.replace('#','%23'),

        iconAnchor  : [22, 28],
        iconSize    : [80, 60],
        popupAnchor : [0, -30],
      }});


    var accuracys = [];
    var markers = [];
    var marker_pos = [];

    Object.keys(positions).forEach(function(key) {{
      if(positions[key].lng){{
        if (positions[key].acc) {{
        // draw a circle
        accuracys.push(
          L.circle([positions[key].lat, positions[key].lng], {{
            color: 'red',
            fillColor: '#f03',
            fillOpacity: 0.15,
            weight: 1,
            opacity: 0.15,
            radius: Math.min(positions[key].acc, 100)
          }}).addTo(mymap)
        );
      }}
      new_marker_pos = [positions[key].lat, positions[key].lng]
      newMarker = L.marker(new_marker_pos, {{ icon: myIcon }}).addTo(mymap);
      newMarker.bindPopup("<b>"+positions[key].ssid+"</b><br>MAC: "+positions[key].mac+"<br/>"+"position type:"+positions[key].type+"<br/>"+"position accuracy:"+positions[key].acc);
      markers.push(newMarker);
      marker_pos.push(new_marker_pos);
      }}
    }});

    var bounds = new L.LatLngBounds(marker_pos);
    mymap.fitBounds(bounds);

  </script>
</body></html>
"""
    return returnstr.format(gps_data=json.dumps(gps_data))
