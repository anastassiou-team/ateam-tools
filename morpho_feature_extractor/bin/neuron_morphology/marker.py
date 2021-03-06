# Copyright 2015-2016 Allen Institute for Brain Science
# This file is part of Allen SDK.
#
# Allen SDK is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Allen SDK is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Allen SDK.  If not, see <http://www.gnu.org/licenses/>.

import csv
import neuron_morphology.constants as constants
from neuron_morphology.validation.result import InvalidMarkerFile
from neuron_morphology.validation.result import MarkerValidationError


class Marker(dict):
    """ Simple dictionary class for handling reconstruction marker objects. """

    CUT_DENDRITE = constants.CUT_DENDRITE
    NO_RECONSTRUCTION = constants.NO_RECONSTRUCTION
    TYPE_30 = constants.TYPE_30

    def __init__(self, *args, **kwargs):
        super(Marker, self).__init__(*args, **kwargs)

        self['original_x'] = self['x']
        self['original_y'] = self['y']
        self['original_z'] = self['z']

        # marker file x,y,z coordinates are offset by a single image-space pixel
        self['x'] -= constants.SPACING[0]
        self['y'] -= constants.SPACING[1]
        self['z'] -= constants.SPACING[2]


def read_marker_file(file_name):
    """ read in a marker file and return a list of dictionaries """

    with open(file_name, 'r') as f:
        rows = csv.DictReader((r for r in f if not r.startswith('#')), fieldnames=['x', 'y', 'z', 'radius', 'shape'
            , 'name', 'comment', 'color_r', 'color_g', 'color_b'])

        markers = []

        for r in rows:
            try:
                markers.append(Marker({'x': float(r['x']),
                                       'y': float(r['y']),
                                       'z': float(r['z']),
                                       'name': int(r['name'])}))

            except ValueError:
                message = "Failed to parse row. One of (x, y, z, name) is missing or invalid"
                raise InvalidMarkerFile([MarkerValidationError(message, r, "Error")])

        return markers
