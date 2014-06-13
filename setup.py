try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Liferay Hotterdeploy',
    'author': 'Jelle Hellemans',
    'url': 'https://github.com/sueastside/liferay-hotterdeploy',
    'download_url': 'https://github.com/sueastside/liferay-hotterdeploy',
    'author_email': 'No, thanks',
    'version': '0.1',
    'install_requires': ['pyinotify', 'pyjavaproperties'],
    'packages': ['hotterdeploy'],
    'scripts': [],
    'name': 'hotterdeploy',
    'entry_points':{
          'console_scripts':['hotterdeploy = hotterdeploy.app:main']
    }
}

setup(**config)
