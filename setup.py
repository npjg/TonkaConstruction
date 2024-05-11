import warnings
from setuptools import setup, Extension

# TODO: Distribute prebuilt wheels for the C bitmap decompression accelerator extension.
#
# For development work, looks like you would use this to compile the 
# C-based image decompressor:
#  python3 setup.py build_ext --inplace
packbits = Extension('PackBits', sources = ['TonkaConstruction/PackBits.c'])
try:
    # TRY TO COMPILE THE C-BASED IMAGE DECOMPRESSOR.
    setup(
        name = 'TonkaConstruction',
        ext_modules = [packbits])
except:
    # RELY ON THE PYTHON FALLBACK.
    warnings.warn('The C PackBits decompression binary is not available on this installation. Expect image decompression to be SLOW.')
    setup(name = 'TonkaConstruction')
