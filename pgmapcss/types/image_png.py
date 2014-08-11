from .default import default
import os
import re
from wand.image import Image

class image_png(default):
    def __init__(self, key, stat):
        default.__init__(self, key, stat)
        self.data = {}

    def compile(self, prop):
        if not os.path.exists(prop['value']):
            print("Image '{}' not found.".format(prop['value']))

        else:
            # Convert SVG to PNG
            m = re.match("([^\/]*)\.svg", prop['value'])
            if m:
                dest = self.stat['icons_dir'] + "/" + m.group(1) + ".png"
                print("svg icon detected. converting '{0}' to '{1}'".format(prop['value'], dest))

                with Image(filename=prop['value']) as img:
                    img.format = 'png'
                    img.save(filename=dest)

                return repr(dest)

        return repr(prop['value'])

    def stat_value(self, prop):
        if prop['value'] is None:
            return prop['value']

        if os.path.exists(prop['value']):
            img = Image(filename=prop['value'])
            self.data[prop['value']] = img.size
            if not prop['key'] in self.stat['global_data']:
                self.stat['global_data'][prop['key']] = {}

            self.stat['global_data'][prop['key']][prop['value']] = img.size

        return prop['value']

    def get_global_data(self):
        self.stat.property_values(self.key)
        return self.data