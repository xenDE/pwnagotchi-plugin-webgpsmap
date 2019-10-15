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

import logging, os, json

OPTIONS = dict()

# called when the plugin is loaded
def on_loaded():
    logging.info("webgpsmap plugin loaded")

# called when <host>:<port>/plugins/<pluginname> is opened
def on_webhook(response, path):
# http://192.168.2.2:8080/plugins/webgpsmap/get-something       path == "/get-something"
    res = get_html()
    response.send_response(200)
    response.send_header('Content-type', 'text/html')
    response.end_headers()
    try:
        response.wfile.write(bytes(res, "utf-8"))
    except Exception as ex:
        logging.error(ex)


def get_gps_data():
# dont know how to become agent
    handshake_dir = "/root/handshakes/"
#    config = agent.config()
#    handshake_dir = config['bettercap']['handshakes']
    gps_data = dict()
    all_files = os.listdir(handshake_dir)
    all_geo_files = [os.path.join(handshake_dir, filename)
                    for filename in all_files
                        if filename.endswith('.geo.json')
                    ]
    print('all_geo_files:')
    print(all_geo_files)
    if all_geo_files:
        logging.info("webgpsmap: Found %d .geo.json files. Fetching positions ...", len(all_geo_files))
        for idx, geo_file in enumerate(all_geo_files):
#                geo_file = np_file.replace('.net-pos.json', '.geo.json')
                if os.path.exists(geo_file):
                    try:
                        with open(geo_file, "r") as json_file:
                            data = json.load(json_file)
                            ssid = os.path.basename(geo_file).replace('.geo.json', '')
                            ssid_name, ssid_id = map( str, ssid.rsplit('_', 1) )
                            gps_data[ssid] = data
                            gps_data[ssid]['name'] = ssid_name
                            gps_data[ssid]['id'] = ssid_id
                    except json.JSONDecodeError as js_e:
                        raise js_e
                    except OSError as os_e:
                        raise os_e
        logging.debug("plugin webgpsmap loaded %d positions: ", len(gps_data))
    return gps_data


def get_html():
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
    Object.keys(positions).forEach(function(key) {{
//      console.log(key, positions[key]);
      var lonLat = new OpenLayers.LonLat( positions[key].location.lng ,positions[key].location.lat )
          .transform(
            new OpenLayers.Projection("EPSG:4326"), // transform from WGS 1984
            map.getProjectionObject() // to Spherical Mercator Projection
          );
      new_marker = new OpenLayers.Marker(lonLat);

      new_marker.events.register('mouseover', new_marker, function(evt) {{
        popup = new OpenLayers.Popup.FramedCloud("Popup",
            lonLat,
            null,
            '<div>'+key+'</div>',
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
    print("gps_data:")
    print(gps_data)
    return returnstr.format(gps_data=json.dumps(gps_data))


