Chameleon
=========

Texture replacement editor for the Quake 3 map format

Features
--------

Chameleon is a standalone GUI-based texture replacement editor written in Python and PyQt. Its main task is replacing a number of textures inside a .map file while applying scale factors and rotation to all affected surfaces. It allows you to:

* Replace old-fashioned textures with high resolution ones without loosing the alignment
* Choose the target shader/texture from a cached database 
* Create and export replacement rulesets for later use 

Dependencies
------------

* Python >= 3.3
* PyQt4
* Pillow
* [Crunch](https://github.com/DaemonEngine/crunch)

OS         | Dependency names
-----------|-----------------
Arch Linux | python python-pyqt4 python-pillow
Debian     | python3 python3-pyqt4 python3-pil

Installation
------------

#### Manual installation

After installing the dependencies, just run chameleon.py with Python.

#### Packages

OS         | Package
-----------|-----------------
Arch Linux | [q3chameleon-git](https://aur.archlinux.org/packages/q3chameleon-git/)

Usage
-----

Always make a backup of your map!
It is recommended that you export the updated map under another name instead of overwriting the old map.

License
-------

> Copyright 2013 Unvanquished Development
>
> This program is free software: you can redistribute it and/or modify
> it under the terms of the GNU General Public License as published by
> the Free Software Foundation, either version 3 of the License, or
> at your option) any later version.
>
> This program is distributed in the hope that it will be useful,
> but WITHOUT ANY WARRANTY; without even the implied warranty of
> MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
> GNU General Public License for more details.
>
> You should have received a copy of the GNU General Public License
> along with this program.  If not, see <http://www.gnu.org/licenses/>.
