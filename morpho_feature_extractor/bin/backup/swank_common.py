import time
import os
import re

SWANK_DIR = os.path.dirname(os.path.realpath(__file__)) + "/../"
UPLOAD_DIR = SWANK_DIR + "upload/"
MASTER_DIR = SWANK_DIR + "morphology_data/master/"
# pixel version of file
#PIXEL_DIR = MASTER_DIR + "pixel/"
# uprighted micron-scale version of file
UPRIGHT_DIR = MASTER_DIR
# if upright not possible, raw micron-scale version of file
RAW_DIR = MASTER_DIR + "non_upright/"

MOUSE_DIR = SWANK_DIR + "morphology_data/mouse/"
MOUSE_AUTO_DIR = MOUSE_DIR + "autotrace/"

MOUSE_INBOUND_DIR = MOUSE_DIR + "to_process/"
MOUSE_INBOUND_NON_UPRIGHT_DIR = MOUSE_DIR + "to_process/non_upright/"

MOUSE_FEATURE_DIR = MOUSE_DIR + "features/"

MOUSE_SWC_DIR = MOUSE_DIR + "swc/"
MOUSE_SWC_NON_UPRIGHT_DIR = MOUSE_DIR + "swc/non_upright/"

MOUSE_HTML_DIR = MOUSE_DIR + "html/"

ARCHIVE_DIR = SWANK_DIR + "morphology_data/master/archive/"

def today_str():
    when = time.strftime("%Y-%m-%d-%H:%M:%S")
    return when

def generate_outfile_name(spec_id):
    return str(spec_id) + ".swc"

def convert_from_titan_linux(file_name):
    # Lookup table mapping project to program
    project_to_program= {
        "neuralcoding": "braintv", 
        '0378': "celltypes",
        'conn': "celltypes",
        'ctyconn': "celltypes",
        'humancelltypes': "celltypes",
        'mousecelltypes': "celltypes",
        'shotconn': "celltypes",
        'synapticphys': "celltypes",
        'whbi': "celltypes",
        'wijem': "celltypes"
    }
    # Tough intermediary state where we have old paths
    # being translated to new paths
    m = re.match('/projects/([^/]+)/vol1/(.*)', file_name)
    if m:
        newpath = os.path.normpath(os.path.join(
            '/allen',
            'programs',
            project_to_program.get(m.group(1),'undefined'),
            'production',
            m.group(1),
            m.group(2)
        ))
        return newpath
    return file_name

def get_spec_id(filename):
    m = re.compile("\d{9}\.swc")
    obj = m.search(filename)
    if obj is not None:
        try:
            return str(obj.group()[:-4])
        except:
            pass
    m = re.compile("\d{6}\.\d\d\.\d\d\.\d\d")
    obj = m.search(filename)
    if obj is not None:
        return specimen_id_from_name(obj.group())
    raise Exception("Unable to figure out specimen ID from file '%s'" % filename)


