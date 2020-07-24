import ateam.sim.singlecell as sc
import os
import os.path
import ateam.data.allensdk_tools as asdk

# Nov. 1 2019
# Changes: use vrest to initialize, double synaptic weight

# bootstrap from initial run
cells_path = "/allen/aibs/mat/tmchartrand/bmtk_networks/singlecell/round1"
cells_inh = os.listdir(os.path.join(cells_path,"IN"))
cells_exc = os.listdir(os.path.join(cells_path,"PC"))

base_path = "/allen/aibs/mat/tmchartrand/bmtk_networks/singlecell/round4/PC"

cells_list = [int(cell) for cell in cells_exc]
inh=False
n_duplicates=10
overwrite=True
level='folder'

sim_path = os.path.join(base_path, "{cell}", "{sim}")
base_id = cells_list[0]
edge_dict = {'syn_weight': 1e-4}
sm_psp = sc.build_epsp_batch(base_id, sim_path.format(cell="base", sim='psp'),
                          inh=inh, n_duplicates=n_duplicates, overwrite=overwrite, edge_dict=edge_dict)

cells_df = asdk.get_cells_ephys_df(manifest_file='/local1/storage/celltypes_data/manifest.json')
for cell_id in cells_list:
    # account for junction potential
    vrest = cells_df.loc[cell_id, 'vrest'] - 14
    config_dict = {"conditions":{"v_init":vrest}}
    sc.copy_sim_for_new_cell(sm_psp, cell_id, sim_path.format(cell=cell_id, sim='psp'), overwrite=True, 
                            config_dict=config_dict)