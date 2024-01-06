from setuptools import setup, Extension

# For development work, looks like you would use this to compile:
#  python3 setup.py build_ext --inplace
packbits = Extension('PackBits', sources = ['TonkaConstruction/PackBits.c'])
setup(
    name = 'TonkaConstruction',
    ext_modules = [packbits])