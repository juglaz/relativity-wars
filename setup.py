from distutils.core import setup
import py2exe
import os


assets = [('assets', [f'assets/{asset}']) for asset in os.listdir('assets')]

setup(
    console=['main.py'],
    data_files=assets
)
