# Alive Cells

Tools to automatically extract Hashlink bytecode from Dead Cells and configure the game to run externally in a more moddable environment.

## Installation

> [!NOTE]
> This project is still in development and is not yet quite ready for public use. It is provided here purely to allow for others to play with the game in ways previously not possible.

### Prerequisites

- [Dead Cells](https://store.steampowered.com/app/588650/Dead_Cells/) for Windows (Any version should work, but this was tested with the Steam version)
- [Python 3.10+](https://www.python.org/downloads/) or [pyenv](https://pyenv-win.github.io/pyenv-win/) and pip (This repository is configured to automatically use 3.10.11 if you have pyenv installed)
- An Internet connection (I hope you have one of these already...)

### Actual Installation

- Clone the repo
- `pip install -r requirements.txt`
- Run `python alivecells.py --help` to see the available commands

## Usage

Currently, a few tools are provided in a single Python script - `alivecells.py`. This script can be run from the command line with the following arguments:

```plaintext
usage: alivecells.py [-h] {install,extract} ...

Extract Hashlink bytecode from Dead Cells executable and prepare it for execution.

positional arguments:
  {install,extract}
    install          Install the Hashlink VM in a given folder and copy over game bytecode and dependencies.
    extract          Extract Hashlink bytecode from the Dead Cells executable.

options:
  -h, --help         show this help message and exit

usage: alivecells.py install [-h] [--output OUTPUT] [--no-extract] [--no-goldberg] dir game_path

positional arguments:
  dir              The directory to install the Hashlink VM in.
  game_path        The path to the Dead Cells game directory.

options:
  -h, --help       show this help message and exit
  --output OUTPUT  The output filename for the Hashlink bytecode.
  --no-extract     Do not extract Hashlink bytecode from the executable - will require you to provide your own hlboot.dat.
  --no-goldberg    Do not use Goldberg Emulator to bypass Steam API issues - don't use this unless you're developing.

usage: alivecells.py extract [-h] [--output OUTPUT] [--in-game-dir] exe_path

positional arguments:
  exe_path         The path to the Dead Cells executable (deadcells.exe, not deadcells_gl.exe).

options:
  -h, --help       show this help message and exit
  --output OUTPUT  The output filename for the Hashlink bytecode.
  --in-game-dir    Save the Hashlink bytecode in the Dead Cells game directory as well as the current directory.
```

## For Modders

This is pretty much uncharted territory when it comes to modding - so here's my best guidance for those who want to try their hand at it:

1. **Install Dead Cells with the Hashlink VM** outside of the Dead Cells game directory - this will allow you to tamper with the game's bytecode without the game refusing to start
2. **Install [Haxe](https://haxe.org/)** - you'll need this to compile the scripts
3. **Disassemble and decompile the bytecode** - you can use [hlbc](https://github.com/Gui-Yom/hlbc), but be warned - not everything can be decompiled (and, in turn, recompiled) correctly, and you'll probably still end up poking and prodding the bytecode with a hex editor (I recommend [ImHex](https://imhex.werwolv.net/) or [REHex](https://rehex.solemnwarning.net/))
4. **Put everything back and hope it works** - you'll need to reassemble the bytecode and put it back in the game directory, then see if it works

## Linux Support

Dead Cells on Linux already has `hlboot.dat` outside of the executable, so you can just use that file directly with your choice of Hashlink VM.

## Roadmap

- [ ] Implement a more user-friendly interface
- [ ] Fix Steam API issues and remove Goldberg workaround
- [ ] Create a proper bytecode patcher/modloader

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. However, the Dead Cells game and its assets are not included in this repository and are subject to their own licensing agreements, and the following licensing exemptions apply:

- The Dead Cells team, Motion Twin, and Evil Empire are hereby permitted to use this software in any way they see fit, including but not limited to modifying, distributing, and selling it.
