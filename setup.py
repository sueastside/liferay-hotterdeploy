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
    'install_requires': [
        'Jinja2',
        'watchdog',
        'pyjavaproperties',
        'pyScss',
        'tornado>=2.2.0',
    ],
    'packages': ['hotterdeploy'],
	'data_files': [('hotterdeploy', ['hotterdeploy/livereload.js','hotterdeploy/index.html'])],
    'scripts': [],
    'name': 'hotterdeploy',
    'entry_points': {
        'console_scripts': [
            'hotterdeploy = hotterdeploy.app:main',
        ],
    }
}

setup(**config)
