import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'usv_sensors'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='USV Team',
    maintainer_email='minji0504407@gmail.com',
    description='USV B1 board sensors: water quality, dual camera, GPS.',
    license='BSD 3-Clause',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'water_quality_node = usv_sensors.water_quality_node:main',
            'camera_node = usv_sensors.camera_node:main',
            'gps_driver_node = usv_sensors.gps_driver_node:main',
        ],
    },
)
