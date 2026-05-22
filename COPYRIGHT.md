<!--
Copyright (C) 2026 Boris Shkylnikov
SPDX-License-Identifier: GPL-3.0-or-later

This file is part of Vox Bee.

Vox Bee is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3.

Vox Bee is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Vox Bee. If not, see <https://www.gnu.org/licenses/>.
-->

# Copyright Coverage

This file covers first-party Vox Bee files that cannot safely carry inline
copyright and license headers because their file formats do not support
comments or embedded notices.

Copyright holder for the listed first-party files:
`Copyright (C) 2026 Boris Shkylnikov`

License for the listed first-party files:
`GPL-3.0-or-later`

Covered files:

- aliases.json
- src/aliases_template.json
- src/commands_template.json
- assets/bee_blue.png
- assets/bee_grey.png
- assets/bee_yellow.png
- src/voxbee.ico
- src/voxbee_off.ico
- src/voxbee_recording.ico
- src/voxbee_full.png
- src/voxbee_preview.png

Excluded from this file:
- Third-party, generated, or bundled artifacts under `venv/`, `dist/`, `build/`,
  `installer_output/`, `models/`, and `bin/`
- External redistributables such as `VC_redist.x64.exe`