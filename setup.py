from setuptools import setup

setup(
    name="electrum-capricoin-server",
    version="1.0",
    scripts=['run_electrum_capricoin_server.py','electrum-capricoin-server'],
    install_requires=['plyvel','jsonrpclib', 'irc>=11', 'x11_hash'],
    package_dir={
        'electrumcapricoinserver':'src'
        },
    py_modules=[
        'electrumcapricoinserver.__init__',
        'electrumcapricoinserver.utils',
        'electrumcapricoinserver.storage',
        'electrumcapricoinserver.deserialize',
        'electrumcapricoinserver.networks',
        'electrumcapricoinserver.blockchain_processor',
        'electrumcapricoinserver.server_processor',
        'electrumcapricoinserver.processor',
        'electrumcapricoinserver.version',
        'electrumcapricoinserver.ircthread',
        'electrumcapricoinserver.stratum_tcp',
        'electrumcapricoinserver.stratum_http'
    ],
    description="Capricoin Electrum Server",
    author="Thomas Voegtlin",
    author_email="thomasv1@gmx.deg",
    maintainer="capricoin",
    maintainer_email="support@capricoin.org",
    license="GNU Affero GPLv3",
    url="https://github.com/Capricoinofficial/electrum-capricoin-server/",
    long_description="""Server for the Lightweight Capricoin Wallet"""
)


