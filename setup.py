from setuptools import setup, find_packages
setup(
    name='ateam',
    version='0.0.1',
    author='Tom Chartrand',
    author_email='tom dot chartrand at alleninstitute dot org',
    description='A-team python tools',
    install_requires=[
        'pandas',
        'numpy',
        'bmtk[bionet]'
    ],
    packages=find_packages(),
    scripts=['bin/run_hpc'],
    entry_points={
        'console_scripts':[
            'run_bionet = ateam.sim.run.run_bionet:main',
            'run_hpc2 = ateam.sim.run.run_hpc:main'
        ]
    },
    platforms='any'
)
