import os
import shutil
import subprocess
import itertools
import csv
import pandas as pd
from collections import defaultdict
# import bmtk.simulator.utils.config as config
from bmtk.simulator.utils.config import ConfigDict
from bmtk.utils.io.spike_trains import PoissonSpikesGenerator
from bmtk.simulator.bionet.biophys_params import BiophysParams
import bmtk.builder.networks as buildnet
import bmtk.utils.sim_setup as setup
import bmtk.analyzer.visualization.spikes as vs

from .config_class import ConfigBuilder
from .spike_input import NodeInput
from ateam.sim.run import runner

ConfigClass = ConfigBuilder

class SimManager(object):
    def __init__(self, config_path="./config.json", sim_folder='', import_nodes=False):
        # TODO: relax constraint on sim_folder as parent dir?
        """Create a SimManager for a simulation defined by a config_file,
        using the parent folder as the simulation folder.
        If config file is not specified, looks for config.json in current directory.
        """
        config_path = os.path.abspath(os.path.join(sim_folder, config_path))
        # assert os.path.isfile(config_path)
        self.config = ConfigClass.from_json(config_path)
        self.configdict = ConfigDict.load(config_path)
        self.sim_folder = os.path.dirname(config_path)
        self._networks_active = {}
        # Dict of net_name: nodes file dict
        self._nodes_dict = {}
        # Dict of (src_name, trg_name): list of edge file dicts
        self._edges_dict = defaultdict(list)
        self.load_networks(import_nodes=import_nodes)

    @staticmethod
    def from_template(config_template, config_file="config.json", sim_folder=None, config_path=None, overwrite=False):
        """
        Create a SimManager from template config file in a new simulation folder.
        Creates folder if it doesn't exist.
        """
        # TODO: clean up template loading (fewer options, configclass?)
        if config_path:
            config_path = os.path.expandvars(os.path.expanduser(config_path))
            sim_folder = os.path.dirname(config_path)
        else:
            sim_folder = sim_folder or os.getcwd()
            sim_folder = os.path.expandvars(os.path.expanduser(sim_folder))
            config_path = os.path.join(sim_folder, config_file)
        # TODO: work with relative paths?
        if not os.path.exists(sim_folder):
            os.makedirs(sim_folder)

        if overwrite or not os.path.isfile(config_path):
            ConfigClass.load_template(config_template, config_path, shared_components=True)
        else:
            Warning("Config file already exists: loading config without template.")

        sm = SimManager(config_path)
        if overwrite:
            sm.clear_output()
        return sm

    @property
    def config_path(self):
        return self.config.path

    @property
    def network_dir(self):
        # TODO: integrate with manifest!
        return "network"

    @property
    def network_builders(self):
        return self._networks_active

    @property
    def networks(self):
        all_nets = list(self._networks_active.keys()) + list(self._nodes_dict.keys())
        return all_nets

    @property
    def networks_saved(self):
        return self._nodes_dict.keys()

    @property
    def files_list(self):
        # return itertools.chain(*self.files_dict.values())
        raise NotImplementedError()

    def default_network(self):
        if len(self.networks)==0:
            raise Exception("No networks found for this simulation.")
        if len(self.networks)==1:
            return self.networks[0]
        raise NotImplementedError()
        
    def new_network(self, net_name):
        net = buildnet.NetworkBuilder(net_name)
        self.add_network(net)
        return net

    def add_network(self, network):
        # TODO: check for name collision
        self._networks_active[network.name] = network

    def add_networks(self, networks):
        for network in networks:
            self.add_network(network)

    def clear_output(self):
        out_dir = os.path.join(self.sim_folder, "output")
        shutil.rmtree(out_dir, ignore_errors=True)

    def save_network_files(self, use_abs_paths=False):
        net_path = self.abspath(self.network_dir)
        if use_abs_paths:
            trim_path = lambda path: path
        else:
            # trim_path = lambda path: os.path.relpath(path, self.sim_folder)
            trim_path = lambda path: os.path.join('$NETWORK_DIR', os.path.relpath(path, net_path))
            
        for name, net in self._networks_active.items():
            if name not in self.networks_saved: # doesn't try to save already loaded networks
                nodes_dict, edge_dicts = net.save(net_path)
                # Convert back to relative paths for config
                for key, path in nodes_dict.items():
                    nodes_dict[key] = trim_path(path)
                self._nodes_dict.update({name: nodes_dict})
                for edgeset in edge_dicts:
                    for key, path in edgeset.items():
                        edgeset[key] = trim_path(path)
                    self._edges_dict[edges_net_pair(edgeset)].append(edgeset)

        nodes = self._nodes_dict.values()
        edges = sum(self._edges_dict.values(), [])
        self.config.update(networks={'nodes':nodes, 'edges':edges})
        self.config.save()

    def save_complete(self, folder_path=''):
        """Save self-contained folder with all simulation files."""
        # TODO: could just copy folder as a first step, but really need to identify external files
        folder_path = folder_path or self.sim_folder
        raise NotImplementedError()

    def save_copy(self, folder_path, overwrite=False, level='folder'):
        """Save a copy of the current sim folder contents to a new directory.
        Remove the output directory from the new folder."""
        if os.path.exists(folder_path):
            if overwrite:
                shutil.rmtree(folder_path)
            else:
                Warning("Folder exists; aborting.")
                return

        # TODO: could use shutil.ignore_patterns here
        # also change relative to absolute paths as needed.
        if level=='folder':
            shutil.copytree(self.sim_folder, folder_path)
        elif level=='network':
            os.makedirs(folder_path)
            shutil.copy2(self.config_path, folder_path)
            shutil.copytree(self.abspath(self.network_dir), os.path.join(folder_path, self.network_dir))
        elif level=='complete':
            self.save_complete(folder_path)

        new_config = os.path.join(folder_path, os.path.basename(self.config_path))
        sm = SimManager(new_config)
        sm.clear_output()
        return sm

    def load_networks(self, import_nodes=False):
        """Loads file paths for networks specified in the config"""
        # Need to use configdict to resolve paths
        if self.configdict.with_networks:
            nets_dict = self.configdict.networks
            # gets network block from config file
            nodes_raw = nets_dict['nodes']
            edges_raw = nets_dict['edges']
            if import_nodes:
                nodes = {}
                for nodeset in nodes_raw:
                    name = nodes_net_name(nodeset)
                    net = self.new_network(name)
                    net.import_nodes(nodeset['nodes_file'], nodeset['node_types_file'], population=None)
                    
            nodes = {nodes_net_name(nodeset):nodeset for nodeset in nodes_raw}
            self._nodes_dict.update(nodes)

            for edgeset in edges_raw:
                self._edges_dict[edges_net_pair(edgeset)].append(edgeset)
        
    def update_node_type_props(self, net_name, props):
        assert(net_name in self.networks_saved)
        update_csv(self.node_types_file(net_name), props)

    def update_edge_type_props(self, src_name, dest_name, props):
        edges = self._edges_dict.get((src_name, dest_name))
        if not edges:
            raise Exception("Could not find edges for the specified networks.")
        if len(edges) > 1:
            Warning("Multiple edge files exist for given pair of networks.")
        edge_dict = edges[0]
        update_csv(self.abspath(edge_dict['edge_types_file']), props)


### Configure inputs and modules
    def abspath(self, filename):
        return os.path.join(self.sim_folder, filename)
    
    def add_current_clamp_complex(self, net_name, input_dict, use_abs_paths=False, name=None):
        name = name or net_name + "_current"
        filename = name + ".csv"
        filepath = self.abspath(filename)
        # TODO: allow specifying gids here, not just list for whole net
        inputs = NodeInput(self._networks_active[net_name].nodes())
        inputs.set_current_inputs(input_dict, filepath)
        inputs = {name: 
            {
            'input_type': 'current_clamp',
            'module': 'IClamp',
            'node_set': net_name,
            'input_file': filepath if use_abs_paths else filename,
            }}
        self.config.update_nested(inputs=inputs)
        self.config.save()

    def add_current_clamp_input(self, input_dict, iclamp_name='IClamp'):
        """Add specified current clamp input to the config.
        """
                
        inputs = {iclamp_name: 
            {
            'input_type': 'current_clamp',
            'module': 'IClamp',
            'node_set': 'all',
            'amp' : input_dict['amp'],
            'delay' : input_dict['delay'],
            'duration' : input_dict['duration']
            }}
        self.config.update_nested(inputs=inputs)
        self.config.save()
    
    def add_spike_input_vector(self, net_name, times, spike_file_name='spike_input.csv', use_abs_paths=False):
        """Write a new spike input file from a vector of times and add it to the config.
        All cells are assigned the same spike times."""

        spike_file = self.abspath(spike_file_name)
        spikes = NodeInput(self._networks_active[net_name].nodes())
        spikes.set_spike_inputs_all_nodes(times, spike_file)
        if use_abs_paths:
            spike_file_name = spike_file
        self.link_spike_input_file(spike_file_name, net_name)

    def add_spike_input_poisson(self, net_name, rate, tstart=0, tstop=2000,
                                 spike_file_name='spike_input.h5', use_abs_paths=False):
        """Write a new spike input file for independent Poisson spiking and add it to the config."""

        net = self._networks_active[net_name]
        spike_file = self.abspath(spike_file_name)
        node_ids = [node.node_id for node in net.nodes_iter()]
        psg = PoissonSpikesGenerator(node_ids, rate, tstart = tstart, tstop=tstop)
        psg.to_hdf5(spike_file)
        if use_abs_paths:
            spike_file_name = spike_file
        self.link_spike_input_file(spike_file_name, net_name)
        
    # TODO: what does trial spec do here? different sets of spikes?
    def link_spike_input_file(self, input_file, net_name, trial=None, name=None):
        """Add specified spikeinput file to the config.
        Note that node ids in the file must match those for the specified net.
        """
        # assert(self._networks_active.has_key(net_name))
        ext = os.path.splitext(input_file)[1][1:]
        name = name or net_name + "_spikes"
        inputs = {name: 
            {
            'input_type': 'spikes',
            'module': ext,
            'input_file': input_file,
            'node_set': net_name,
            'trial': trial
            }}
        self.config.update_nested(inputs=inputs)
        self.config.save()

    def add_ecp_report(self, electrode_file=None, cells='all', file_name='ecp.h5', locs=[[0,0,0]], save_contributions=False):
        if electrode_file is None:
            electrode_file = 'electrode.csv'
            self.write_electrode_file(locs, self.abspath(electrode_file))

        reports = {'ecp_report': {
            'cells': cells,
            'variable_name': 'v',
            'module': 'extracellular',
            'electrode_positions': electrode_file,
            'file_name': file_name,
            'electrode_channels': 'all',
            'contributions_dir': 'ecp_contributions' if save_contributions else None
        }}
        self.config.update_nested(reports=reports)


    @staticmethod
    def write_electrode_file(locs, csv_file_name):
        import csv
        with open(csv_file_name, 'w') as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=' ')
            csv_writer.writerow(['channel', 'x_pos', 'y_pos', 'z_pos'])
            for i, loc in enumerate(locs):
                csv_writer.writerow([i] + [str(x) for x in loc])


    def add_membrane_report(self, name='membrane_report', variables=['v'], cells='all', sections='soma',
                            file_name=None, **kwargs):
        reports = {name: {
            'module': 'membrane_report',
            'variable_name': variables,
            'cells': cells,
            'file_name': file_name or '{name}.h5'.format(name=name),
            'sections': sections
            }}
        
        # use kwargs to include distance specifier for recording segments by location
        reports[name].update(**kwargs)
        self.config.update_nested(reports=reports)
        self.config.save()
    
    def get_single_net(self):
        networks = self.networks
        if len(networks)==1:
            return networks[0]
        else:
            raise Exception("More than one network in simulation, must specify network name.")

    def nodes_file(self, net=None):
        # TODO: check net in networks first?
        # return self.abspath("{}_nodes.h5".format(net))
        if net is None:
            net = self.get_single_net()
        path = self._nodes_dict[net]["nodes_file"]
        return self.abspath(path)
        
    def node_types_file(self, net=None):
        # TODO: check net in networks first?
        # return self.abspath("{}_node_types.csv".format(net))
        if net is None:
            net = self.get_single_net()
        path = self._nodes_dict[net]["node_types_file"]
        return self.abspath(path)

    def get_dynamics_param_vals(self, params_list, gid=0):
        node_types = pd.read_csv(self.node_types_file(), delimiter=' ')

        dynamics_file = node_types.loc[gid, 'dynamics_params']
        dynamics_path = os.path.join(
            self.configdict.biophysical_neuron_models_dir,
            dynamics_file
        )
        dp = BiophysParams.from_json(dynamics_path)
        return [float(dp.get_nested("genome."+param)) for param in params_list]

    @property
    def spikes_file(self):
        return self.configdict.spikes_file

    @property
    def sim_time(self):
        return self.config['run']['tstop']

    @sim_time.setter
    def sim_time(self, time):
        self.config['run']['tstop'] = time
        self.config.save()

    @property
    def sim_timestep(self):
        return self.config['run']['dt']
    
    @sim_timestep.setter
    def sim_timestep(self, dt):
        self.config['run']['dt'] = dt
        self.config.save()


    def run_bionet(self):
        self.config.save()
        return runner.run_bionet(self.config_path)
        
    def run_bionet_mpi(self, ncores=1):
        self.config.save()
        runner.run_bionet_mpi(self.config_path, ncores)

    def plot_raster(self, net, **kwargs):
        return vs.plot_spikes(self.nodes_file(net), self.node_types_file(net), self.spikes_file, **kwargs)

    def plot_rates(self, net, **kwargs):
        return vs.plot_rates(self.nodes_file(net), self.node_types_file(net), self.spikes_file, **kwargs)


def nodes_net_name(nodeset):
    """Extract the network name from nodes file dict as specified in config"""
    nodes_file = nodeset['nodes_file']
    net_name = os.path.basename(nodes_file).split('_')[0]
    return net_name

def edges_net_pair(edgeset):
    """Extract the source and target network names from edges file dict as specified in config.
    Return a tuple (source name, target name)."""
    edge_file = edgeset['edges_file']
    src, dest = os.path.basename(edge_file).split('_')[0:2]
    return (src, dest)

def update_csv(csv_path, props):
    with open(csv_path) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=' ')
        rows = [dict(row, **props) for row in reader]
    with open(csv_path, 'w',) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys(), delimiter=' ')
        writer.writeheader()
        writer.writerows(rows)

def create_singlecell_default(cell_id, sim_folder, sim_time=500, active=True, directed=True, node_dict={}, config_dict={}, config_template=None):
    import ateam.sim.setup.default_props as defaults
    network = 'single'
    config_template = config_template or "/allen/aibs/mat/tmchartrand/bmtk_networks/biophys_components_shared/default_config.json"

    sm = SimManager.from_template(config_template=config_template, overwrite=True, sim_folder=sim_folder)

    node_props = defaults.cellprops_active(cell_id, directed) if active else defaults.cellprops_peri(cell_id, directed)
    node_props.update(node_dict)
    net = sm.new_network(network)
    net.add_nodes(N=1, **node_props)

    sm.sim_time = sim_time
    sm.config.update_nested(config_dict)
    sm.save_network_files(use_abs_paths=True)
    return sm