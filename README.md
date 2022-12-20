# OpenDeviceController watcher

## Description

This service is part of [OpenDeviceController](https://github.com/a2mSystemes/OpenDController) system. It aims at watch a folder for modifications/creations/deletion
of Resolume Arena Compositions. When requested, this service launch the selected composition with resolume Arena. 

## Install

```ps
git clone https://github.com/a2msystemes/python-watcher
cd ./python-watcher
python -m venv venv
.\.venv\Scripts\Activate.ps1
python - m ensurepip --upgrade
pip install -r .\requirements.txt
```

## Usage

```
python ./watcher.py
```

## Author
- Ange-Marie MAURIN  [a-m.maurin@a2msystemes.fr](mailto:a-m.maurin@a2msystemes.fr)

## License

OpenDController is licensed under the GNU General Public License v3 (GPL-3) (http://www.gnu.org/copyleft/gpl.html).

Interested in a sublicense agreement for use of OpenDController in a non-free/restrictive environment? 
Contact me at [<a-m.maurin@a2mSystemes.fr>](mailto://a-m.maurin@a2mSystemes.fr)