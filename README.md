# <img src="https://raw.githubusercontent.com/npjg/TonkaConstruction/main/.github/favicon.svg" width="32" height="32" alt="Tonka Construction"> Tonka Construction
Hey there little truckster!

This was one of the first computer games I ever played. If I recall correctly, I got the CD-ROM from a yard sale... where I've gotten most games I've ever played. This game brought much enjoyment to me as a youngster.

# Support Me!
If you like my reverse-engineering work, you can [buy me a matcha latte](https://www.buymeacoffee.com/natster) 🍵! 

## Usage
Installing the PyPI package will also install a `TonkaConstruction` script that can be invoked from the command line as follows:
```
#                 Input directory   Export directory
#                 ...............   .................
TonkaConstruction ~/TONKA/DATA      ~/TonkaExtract
```

## Testing
Currently there is no support for running tests from CI/CD because these services won't have the (large) game files necessary to test this library. Currently all tests are run locally with the files for each known Tonka version in the `tests/test_data` directory.

## Acknowledgements
The Tonka truck icon used as this repository's icon was taken from the Tonka Construction CD-ROM.