<!-- generated: scripts/governance/render_third_party_notices.py; do not edit directly -->

# Third-Party Notices

This file is the machine-generated third-party rights ledger for the tracked public repository surface.

## Scope

- Python runtime inventory comes from the canonical `uv sync --frozen --extra dev --python-platform aarch64-unknown-linux-gnu` environment, using a throwaway temp uv environment instead of root `.venv` or repo-owned runtime roots.
- Web runtime inventory comes from `apps/web/package-lock.json` and excludes `dev=true` packages.
- `UNKNOWN` means the package metadata did not expose a machine-readable license field/classifier in this inventory pass; it is a follow-up item, not a silent pass.

## Summary

| Ecosystem | Packages | UNKNOWN license declarations |
| --- | ---: | ---: |
| Python runtime | 98 | 0 |
| Web runtime | 287 | 0 |

## Python Runtime Packages

| Package | Version | License | Evidence Source |
| --- | --- | --- | --- |
| `aiohappyeyeballs` | `2.6.1` | `PSF-2.0` | `license-field` |
| `aiohttp` | `3.13.4` | `Apache-2.0 AND MIT` | `license-field` |
| `aiosignal` | `1.4.0` | `Apache 2.0` | `license-field` |
| `annotated-doc` | `0.0.4` | `MIT` | `license-expression` |
| `annotated-types` | `0.7.0` | `MIT License` | `classifier` |
| `anyio` | `4.12.1` | `MIT` | `license-expression` |
| `attrs` | `25.4.0` | `MIT` | `license-expression` |
| `babel` | `2.18.0` | `BSD-3-Clause` | `license-field` |
| `certifi` | `2026.1.4` | `MPL-2.0` | `license-field` |
| `cffi` | `2.0.0` | `MIT` | `license-expression` |
| `charset-normalizer` | `3.4.4` | `MIT` | `license-field` |
| `click` | `8.3.1` | `BSD-3-Clause` | `license-expression` |
| `courlan` | `1.3.2` | `Apache 2.0` | `license-field` |
| `coverage` | `7.13.4` | `Apache-2.0` | `license-field` |
| `cryptography` | `46.0.7` | `Apache-2.0 OR BSD-3-Clause` | `license-expression` |
| `dateparser` | `1.3.0` | `BSD` | `license-field` |
| `defusedxml` | `0.7.1` | `PSFL` | `license-field` |
| `distro` | `1.9.0` | `Apache License, Version 2.0` | `license-field` |
| `execnet` | `2.1.2` | `MIT` | `license-expression` |
| `fastapi` | `0.129.0` | `MIT` | `license-expression` |
| `frozenlist` | `1.8.0` | `Apache-2.0` | `license-field` |
| `google-auth` | `2.48.0` | `Apache 2.0` | `license-field` |
| `google-genai` | `1.64.0` | `Apache-2.0` | `license-expression` |
| `greenlet` | `3.3.2` | `MIT AND PSF-2.0` | `license-expression` |
| `h11` | `0.16.0` | `MIT` | `license-field` |
| `htmldate` | `1.9.4` | `Apache 2.0` | `license-field` |
| `httpcore` | `1.0.9` | `BSD-3-Clause` | `license-expression` |
| `httpx` | `0.28.1` | `BSD-3-Clause` | `license-field` |
| `httpx-sse` | `0.4.3` | `MIT` | `license-field` |
| `idna` | `3.11` | `BSD-3-Clause` | `license-expression` |
| `iniconfig` | `2.3.0` | `MIT` | `license-expression` |
| `jsonschema` | `4.26.0` | `MIT` | `license-expression` |
| `jsonschema-specifications` | `2025.9.1` | `MIT` | `license-expression` |
| `jusText` | `3.0.2` | `The BSD 2-Clause License` | `license-field` |
| `libcst` | `1.8.6` | `All contributions towards LibCST are MIT licensed.

Some Python files have been derived from the standard library and are therefore
PSF licensed. Modifications on these files are dual licensed (both MIT and
PSF). These files are:

- libcst/_parser/base_parser.py
- libcst/_parser/parso/utils.py
- libcst/_parser/parso/pgen2/generator.py
- libcst/_parser/parso/pgen2/grammar_parser.py
- libcst/_parser/parso/python/py_token.py
- libcst/_parser/parso/python/tokenize.py
- libcst/_parser/parso/tests/test_fstring.py
- libcst/_parser/parso/tests/test_tokenize.py
- libcst/_parser/parso/tests/test_utils.py
- native/libcst/src/tokenizer/core/mod.rs
- native/libcst/src/tokenizer/core/string_types.rs

Some Python files have been taken from dataclasses and are therefore Apache
licensed. Modifications on these files are licensed under Apache 2.0 license.
These files are:

- libcst/_add_slots.py

-------------------------------------------------------------------------------

MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

-------------------------------------------------------------------------------

PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2

1. This LICENSE AGREEMENT is between the Python Software Foundation
("PSF"), and the Individual or Organization ("Licensee") accessing and
otherwise using this software ("Python") in source or binary form and
its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
analyze, test, perform and/or display publicly, prepare derivative works,
distribute, and otherwise use Python alone or in any derivative version,
provided, however, that PSF's License Agreement and PSF's notice of copyright,
i.e., "Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
2011, 2012, 2013, 2014, 2015 Python Software Foundation; All Rights Reserved"
are retained in Python alone or in any derivative version prepared by Licensee.

3. In the event Licensee prepares a derivative work that is based on
or incorporates Python or any part thereof, and wants to make
the derivative work available to others as provided herein, then
Licensee hereby agrees to include in any such work a brief summary of
the changes made to Python.

4. PSF is making Python available to Licensee on an "AS IS"
basis.  PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
INFRINGE ANY THIRD PARTY RIGHTS.

5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

6. This License Agreement will automatically terminate upon a material
breach of its terms and conditions.

7. Nothing in this License Agreement shall be deemed to create any
relationship of agency, partnership, or joint venture between PSF and
Licensee.  This License Agreement does not grant permission to use PSF
trademarks or trade name in a trademark sense to endorse or promote
products or services of Licensee, or any third party.

8. By copying, installing or otherwise using Python, Licensee
agrees to be bound by the terms and conditions of this License
Agreement.

-------------------------------------------------------------------------------

APACHE LICENSE, VERSION 2.0

http://www.apache.org/licenses/LICENSE-2.0` | `license-field` |
| `linkify-it-py` | `2.0.3` | `MIT` | `license-field` |
| `lxml` | `6.1.0` | `BSD-3-Clause` | `license-field` |
| `lxml_html_clean` | `0.4.4` | `BSD-3-Clause` | `license-field` |
| `Markdown` | `3.10.2` | `BSD-3-Clause` | `license-expression` |
| `markdown-it-py` | `4.0.0` | `MIT License` | `classifier` |
| `mcp` | `1.26.0` | `MIT` | `license-field` |
| `mdit-py-plugins` | `0.5.0` | `MIT License` | `classifier` |
| `mdurl` | `0.1.2` | `MIT License` | `classifier` |
| `multidict` | `6.7.1` | `Apache License 2.0` | `license-field` |
| `mutmut` | `3.5.0` | `BSD-3-Clause` | `license-expression` |
| `nexus-rpc` | `1.3.0` | `MIT` | `license-expression` |
| `packaging` | `26.0` | `Apache-2.0 OR BSD-2-Clause` | `license-expression` |
| `platformdirs` | `4.9.2` | `MIT` | `license-expression` |
| `pluggy` | `1.6.0` | `MIT` | `license-field` |
| `propcache` | `0.4.1` | `Apache-2.0` | `license-field` |
| `protobuf` | `6.33.5` | `3-Clause BSD License` | `license-field` |
| `psycopg` | `3.3.3` | `LGPL-3.0-only` | `license-expression` |
| `psycopg-binary` | `3.3.3` | `LGPL-3.0-only` | `license-expression` |
| `pyasn1` | `0.6.3` | `BSD-2-Clause` | `license-field` |
| `pyasn1_modules` | `0.4.2` | `BSD` | `license-field` |
| `pycparser` | `3.0` | `BSD-3-Clause` | `license-expression` |
| `pydantic` | `2.12.5` | `MIT` | `license-expression` |
| `pydantic-settings` | `2.13.1` | `MIT` | `license-expression` |
| `pydantic_core` | `2.41.5` | `MIT` | `license-expression` |
| `Pygments` | `2.20.0` | `BSD-2-Clause` | `license-expression` |
| `PyJWT` | `2.12.1` | `MIT` | `license-expression` |
| `pytest` | `9.0.3` | `MIT` | `license-expression` |
| `pytest-cov` | `6.3.0` | `MIT` | `license-field` |
| `pytest-rerunfailures` | `15.1` | `MPL-2.0` | `license-field` |
| `pytest-xdist` | `3.8.0` | `MIT` | `license-expression` |
| `python-dateutil` | `2.9.0.post0` | `Dual License` | `license-field` |
| `python-dotenv` | `1.2.2` | `BSD-3-Clause` | `license-field` |
| `python-multipart` | `0.0.26` | `Apache-2.0` | `license-expression` |
| `pytz` | `2026.1.post1` | `MIT` | `license-field` |
| `PyYAML` | `6.0.3` | `MIT` | `license-field` |
| `referencing` | `0.37.0` | `MIT` | `license-expression` |
| `regex` | `2026.2.28` | `Apache-2.0 AND CNRI-Python` | `license-expression` |
| `requests` | `2.33.0` | `Apache-2.0` | `license-field` |
| `rich` | `14.3.3` | `MIT` | `license-field` |
| `rpds-py` | `0.30.0` | `MIT` | `license-expression` |
| `rsa` | `4.9.1` | `Apache-2.0` | `license-field` |
| `setproctitle` | `1.3.7` | `BSD-3-Clause` | `license-field` |
| `six` | `1.17.0` | `MIT` | `license-field` |
| `sniffio` | `1.3.1` | `MIT OR Apache-2.0` | `license-field` |
| `SQLAlchemy` | `2.0.46` | `MIT` | `license-field` |
| `sse-starlette` | `3.2.0` | `BSD-3-Clause` | `license-expression` |
| `starlette` | `0.52.1` | `BSD-3-Clause` | `license-expression` |
| `temporalio` | `1.23.0` | `MIT` | `license-expression` |
| `tenacity` | `9.1.4` | `Apache 2.0` | `license-field` |
| `textual` | `8.0.0` | `MIT` | `license-field` |
| `tld` | `0.13.2` | `MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later` | `license-expression` |
| `trafilatura` | `1.12.2` | `Apache-2.0` | `license-field` |
| `types-protobuf` | `6.32.1.20260221` | `Apache-2.0` | `license-expression` |
| `typing-inspection` | `0.4.2` | `MIT` | `license-expression` |
| `typing_extensions` | `4.15.0` | `PSF-2.0` | `license-expression` |
| `tzdata` | `2025.3` | `Apache-2.0` | `license-field` |
| `tzlocal` | `5.3.1` | `MIT` | `license-field` |
| `uc-micro-py` | `1.0.3` | `MIT` | `license-field` |
| `urllib3` | `2.6.3` | `MIT` | `license-expression` |
| `uvicorn` | `0.41.0` | `BSD-3-Clause` | `license-expression` |
| `websockets` | `15.0.1` | `BSD-3-Clause` | `license-field` |
| `yarl` | `1.22.0` | `Apache-2.0` | `license-field` |
| `youtube-transcript-api` | `1.2.4` | `MIT` | `license-field` |

## Web Runtime Packages

| Package | Version | License | Evidence Source |
| --- | --- | --- | --- |
| `@alloc/quick-lru` | `5.2.0` | `MIT` | `package-lock` |
| `@emnapi/core` | `1.8.1` | `MIT` | `package-lock` |
| `@emnapi/runtime` | `1.8.1` | `MIT` | `package-lock` |
| `@emnapi/runtime` | `1.8.1` | `MIT` | `package-lock` |
| `@emnapi/wasi-threads` | `1.1.0` | `MIT` | `package-lock` |
| `@floating-ui/core` | `1.7.5` | `MIT` | `package-lock` |
| `@floating-ui/dom` | `1.7.6` | `MIT` | `package-lock` |
| `@floating-ui/react-dom` | `2.1.8` | `MIT` | `package-lock` |
| `@floating-ui/utils` | `0.2.11` | `MIT` | `package-lock` |
| `@img/colour` | `1.0.0` | `MIT` | `package-lock` |
| `@img/sharp-darwin-arm64` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-darwin-x64` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-libvips-darwin-arm64` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-libvips-darwin-x64` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-libvips-linux-arm` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-libvips-linux-arm64` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-libvips-linux-ppc64` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-libvips-linux-riscv64` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-libvips-linux-s390x` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-libvips-linux-x64` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-libvips-linuxmusl-arm64` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-libvips-linuxmusl-x64` | `1.2.4` | `LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-linux-arm` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-linux-arm64` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-linux-ppc64` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-linux-riscv64` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-linux-s390x` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-linux-x64` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-linuxmusl-arm64` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-linuxmusl-x64` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `@img/sharp-wasm32` | `0.34.5` | `Apache-2.0 AND LGPL-3.0-or-later AND MIT` | `package-lock` |
| `@img/sharp-win32-arm64` | `0.34.5` | `Apache-2.0 AND LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-win32-ia32` | `0.34.5` | `Apache-2.0 AND LGPL-3.0-or-later` | `package-lock` |
| `@img/sharp-win32-x64` | `0.34.5` | `Apache-2.0 AND LGPL-3.0-or-later` | `package-lock` |
| `@jridgewell/gen-mapping` | `0.3.13` | `MIT` | `package-lock` |
| `@jridgewell/remapping` | `2.3.5` | `MIT` | `package-lock` |
| `@jridgewell/resolve-uri` | `3.1.2` | `MIT` | `package-lock` |
| `@jridgewell/sourcemap-codec` | `1.5.5` | `MIT` | `package-lock` |
| `@jridgewell/trace-mapping` | `0.3.31` | `MIT` | `package-lock` |
| `@napi-rs/wasm-runtime` | `1.1.1` | `MIT` | `package-lock` |
| `@next/env` | `16.2.3` | `MIT` | `package-lock` |
| `@next/swc-darwin-arm64` | `16.2.3` | `MIT` | `package-lock` |
| `@next/swc-darwin-x64` | `16.2.3` | `MIT` | `package-lock` |
| `@next/swc-linux-arm64-gnu` | `16.2.3` | `MIT` | `package-lock` |
| `@next/swc-linux-arm64-musl` | `16.2.3` | `MIT` | `package-lock` |
| `@next/swc-linux-x64-gnu` | `16.2.3` | `MIT` | `package-lock` |
| `@next/swc-linux-x64-musl` | `16.2.3` | `MIT` | `package-lock` |
| `@next/swc-win32-arm64-msvc` | `16.2.3` | `MIT` | `package-lock` |
| `@next/swc-win32-x64-msvc` | `16.2.3` | `MIT` | `package-lock` |
| `@radix-ui/number` | `1.1.1` | `MIT` | `package-lock` |
| `@radix-ui/primitive` | `1.1.3` | `MIT` | `package-lock` |
| `@radix-ui/react-accessible-icon` | `1.1.7` | `MIT` | `package-lock` |
| `@radix-ui/react-accordion` | `1.2.12` | `MIT` | `package-lock` |
| `@radix-ui/react-alert-dialog` | `1.1.15` | `MIT` | `package-lock` |
| `@radix-ui/react-arrow` | `1.1.7` | `MIT` | `package-lock` |
| `@radix-ui/react-aspect-ratio` | `1.1.7` | `MIT` | `package-lock` |
| `@radix-ui/react-avatar` | `1.1.10` | `MIT` | `package-lock` |
| `@radix-ui/react-checkbox` | `1.3.3` | `MIT` | `package-lock` |
| `@radix-ui/react-collapsible` | `1.1.12` | `MIT` | `package-lock` |
| `@radix-ui/react-collection` | `1.1.7` | `MIT` | `package-lock` |
| `@radix-ui/react-compose-refs` | `1.1.2` | `MIT` | `package-lock` |
| `@radix-ui/react-context` | `1.1.2` | `MIT` | `package-lock` |
| `@radix-ui/react-context-menu` | `2.2.16` | `MIT` | `package-lock` |
| `@radix-ui/react-dialog` | `1.1.15` | `MIT` | `package-lock` |
| `@radix-ui/react-direction` | `1.1.1` | `MIT` | `package-lock` |
| `@radix-ui/react-dismissable-layer` | `1.1.11` | `MIT` | `package-lock` |
| `@radix-ui/react-dropdown-menu` | `2.1.16` | `MIT` | `package-lock` |
| `@radix-ui/react-focus-guards` | `1.1.3` | `MIT` | `package-lock` |
| `@radix-ui/react-focus-scope` | `1.1.7` | `MIT` | `package-lock` |
| `@radix-ui/react-form` | `0.1.8` | `MIT` | `package-lock` |
| `@radix-ui/react-hover-card` | `1.1.15` | `MIT` | `package-lock` |
| `@radix-ui/react-id` | `1.1.1` | `MIT` | `package-lock` |
| `@radix-ui/react-label` | `2.1.7` | `MIT` | `package-lock` |
| `@radix-ui/react-menu` | `2.1.16` | `MIT` | `package-lock` |
| `@radix-ui/react-menubar` | `1.1.16` | `MIT` | `package-lock` |
| `@radix-ui/react-navigation-menu` | `1.2.14` | `MIT` | `package-lock` |
| `@radix-ui/react-one-time-password-field` | `0.1.8` | `MIT` | `package-lock` |
| `@radix-ui/react-password-toggle-field` | `0.1.3` | `MIT` | `package-lock` |
| `@radix-ui/react-popover` | `1.1.15` | `MIT` | `package-lock` |
| `@radix-ui/react-popper` | `1.2.8` | `MIT` | `package-lock` |
| `@radix-ui/react-portal` | `1.1.9` | `MIT` | `package-lock` |
| `@radix-ui/react-presence` | `1.1.5` | `MIT` | `package-lock` |
| `@radix-ui/react-primitive` | `2.1.3` | `MIT` | `package-lock` |
| `@radix-ui/react-progress` | `1.1.7` | `MIT` | `package-lock` |
| `@radix-ui/react-radio-group` | `1.3.8` | `MIT` | `package-lock` |
| `@radix-ui/react-roving-focus` | `1.1.11` | `MIT` | `package-lock` |
| `@radix-ui/react-scroll-area` | `1.2.10` | `MIT` | `package-lock` |
| `@radix-ui/react-select` | `2.2.6` | `MIT` | `package-lock` |
| `@radix-ui/react-separator` | `1.1.7` | `MIT` | `package-lock` |
| `@radix-ui/react-slider` | `1.3.6` | `MIT` | `package-lock` |
| `@radix-ui/react-slot` | `1.2.3` | `MIT` | `package-lock` |
| `@radix-ui/react-switch` | `1.2.6` | `MIT` | `package-lock` |
| `@radix-ui/react-tabs` | `1.1.13` | `MIT` | `package-lock` |
| `@radix-ui/react-toast` | `1.2.15` | `MIT` | `package-lock` |
| `@radix-ui/react-toggle` | `1.1.10` | `MIT` | `package-lock` |
| `@radix-ui/react-toggle-group` | `1.1.11` | `MIT` | `package-lock` |
| `@radix-ui/react-toolbar` | `1.1.11` | `MIT` | `package-lock` |
| `@radix-ui/react-tooltip` | `1.2.8` | `MIT` | `package-lock` |
| `@radix-ui/react-use-callback-ref` | `1.1.1` | `MIT` | `package-lock` |
| `@radix-ui/react-use-controllable-state` | `1.2.2` | `MIT` | `package-lock` |
| `@radix-ui/react-use-effect-event` | `0.0.2` | `MIT` | `package-lock` |
| `@radix-ui/react-use-escape-keydown` | `1.1.1` | `MIT` | `package-lock` |
| `@radix-ui/react-use-is-hydrated` | `0.1.0` | `MIT` | `package-lock` |
| `@radix-ui/react-use-layout-effect` | `1.1.1` | `MIT` | `package-lock` |
| `@radix-ui/react-use-previous` | `1.1.1` | `MIT` | `package-lock` |
| `@radix-ui/react-use-rect` | `1.1.1` | `MIT` | `package-lock` |
| `@radix-ui/react-use-size` | `1.1.1` | `MIT` | `package-lock` |
| `@radix-ui/react-visually-hidden` | `1.2.3` | `MIT` | `package-lock` |
| `@radix-ui/rect` | `1.1.1` | `MIT` | `package-lock` |
| `@sourceharbor/sdk` | `0.1.19` | `MIT` | `package-lock` |
| `@swc/helpers` | `0.5.15` | `Apache-2.0` | `package-lock` |
| `@tailwindcss/node` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-android-arm64` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-darwin-arm64` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-darwin-x64` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-freebsd-x64` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-linux-arm-gnueabihf` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-linux-arm64-gnu` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-linux-arm64-musl` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-linux-x64-gnu` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-linux-x64-musl` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-wasm32-wasi` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-win32-arm64-msvc` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/oxide-win32-x64-msvc` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/postcss` | `4.2.2` | `MIT` | `package-lock` |
| `@tailwindcss/typography` | `0.5.19` | `MIT` | `package-lock` |
| `@tybys/wasm-util` | `0.10.1` | `MIT` | `package-lock` |
| `@types/debug` | `4.1.12` | `MIT` | `package-lock` |
| `@types/estree` | `1.0.8` | `MIT` | `package-lock` |
| `@types/estree-jsx` | `1.0.5` | `MIT` | `package-lock` |
| `@types/hast` | `3.0.4` | `MIT` | `package-lock` |
| `@types/mdast` | `4.0.4` | `MIT` | `package-lock` |
| `@types/ms` | `2.1.0` | `MIT` | `package-lock` |
| `@types/react` | `19.2.14` | `MIT` | `package-lock` |
| `@types/react-dom` | `19.2.3` | `MIT` | `package-lock` |
| `@types/unist` | `3.0.3` | `MIT` | `package-lock` |
| `@types/unist` | `2.0.11` | `MIT` | `package-lock` |
| `@ungap/structured-clone` | `1.3.0` | `ISC` | `package-lock` |
| `aria-hidden` | `1.2.6` | `MIT` | `package-lock` |
| `bail` | `2.0.2` | `MIT` | `package-lock` |
| `baseline-browser-mapping` | `2.10.0` | `Apache-2.0` | `package-lock` |
| `caniuse-lite` | `1.0.30001770` | `CC-BY-4.0` | `package-lock` |
| `ccount` | `2.0.1` | `MIT` | `package-lock` |
| `character-entities` | `2.0.2` | `MIT` | `package-lock` |
| `character-entities-html4` | `2.1.0` | `MIT` | `package-lock` |
| `character-entities-legacy` | `3.0.0` | `MIT` | `package-lock` |
| `character-reference-invalid` | `2.0.1` | `MIT` | `package-lock` |
| `class-variance-authority` | `0.7.1` | `Apache-2.0` | `package-lock` |
| `client-only` | `0.0.1` | `MIT` | `package-lock` |
| `clsx` | `2.1.1` | `MIT` | `package-lock` |
| `comma-separated-tokens` | `2.0.3` | `MIT` | `package-lock` |
| `cssesc` | `3.0.0` | `MIT` | `package-lock` |
| `csstype` | `3.2.3` | `MIT` | `package-lock` |
| `debug` | `4.4.3` | `MIT` | `package-lock` |
| `decode-named-character-reference` | `1.3.0` | `MIT` | `package-lock` |
| `dequal` | `2.0.3` | `MIT` | `package-lock` |
| `detect-libc` | `2.1.2` | `Apache-2.0` | `package-lock` |
| `detect-node-es` | `1.1.0` | `MIT` | `package-lock` |
| `devlop` | `1.1.0` | `MIT` | `package-lock` |
| `enhanced-resolve` | `5.20.1` | `MIT` | `package-lock` |
| `escape-string-regexp` | `5.0.0` | `MIT` | `package-lock` |
| `estree-util-is-identifier-name` | `3.0.0` | `MIT` | `package-lock` |
| `extend` | `3.0.2` | `MIT` | `package-lock` |
| `geist` | `1.7.0` | `SIL OPEN FONT LICENSE` | `package-lock` |
| `get-nonce` | `1.0.1` | `MIT` | `package-lock` |
| `graceful-fs` | `4.2.11` | `ISC` | `package-lock` |
| `hast-util-to-jsx-runtime` | `2.3.6` | `MIT` | `package-lock` |
| `hast-util-whitespace` | `3.0.0` | `MIT` | `package-lock` |
| `html-url-attributes` | `3.0.1` | `MIT` | `package-lock` |
| `inline-style-parser` | `0.2.7` | `MIT` | `package-lock` |
| `is-alphabetical` | `2.0.1` | `MIT` | `package-lock` |
| `is-alphanumerical` | `2.0.1` | `MIT` | `package-lock` |
| `is-decimal` | `2.0.1` | `MIT` | `package-lock` |
| `is-hexadecimal` | `2.0.1` | `MIT` | `package-lock` |
| `is-plain-obj` | `4.1.0` | `MIT` | `package-lock` |
| `jiti` | `2.6.1` | `MIT` | `package-lock` |
| `lightningcss` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-android-arm64` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-darwin-arm64` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-darwin-x64` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-freebsd-x64` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-linux-arm-gnueabihf` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-linux-arm64-gnu` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-linux-arm64-musl` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-linux-x64-gnu` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-linux-x64-musl` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-win32-arm64-msvc` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `lightningcss-win32-x64-msvc` | `1.32.0` | `MPL-2.0` | `package-lock` |
| `longest-streak` | `3.1.0` | `MIT` | `package-lock` |
| `lucide-react` | `1.7.0` | `ISC` | `package-lock` |
| `magic-string` | `0.30.21` | `MIT` | `package-lock` |
| `markdown-table` | `3.0.4` | `MIT` | `package-lock` |
| `mdast-util-find-and-replace` | `3.0.2` | `MIT` | `package-lock` |
| `mdast-util-from-markdown` | `2.0.2` | `MIT` | `package-lock` |
| `mdast-util-gfm` | `3.1.0` | `MIT` | `package-lock` |
| `mdast-util-gfm-autolink-literal` | `2.0.1` | `MIT` | `package-lock` |
| `mdast-util-gfm-footnote` | `2.1.0` | `MIT` | `package-lock` |
| `mdast-util-gfm-strikethrough` | `2.0.0` | `MIT` | `package-lock` |
| `mdast-util-gfm-table` | `2.0.0` | `MIT` | `package-lock` |
| `mdast-util-gfm-task-list-item` | `2.0.0` | `MIT` | `package-lock` |
| `mdast-util-mdx-expression` | `2.0.1` | `MIT` | `package-lock` |
| `mdast-util-mdx-jsx` | `3.2.0` | `MIT` | `package-lock` |
| `mdast-util-mdxjs-esm` | `2.0.1` | `MIT` | `package-lock` |
| `mdast-util-phrasing` | `4.1.0` | `MIT` | `package-lock` |
| `mdast-util-to-hast` | `13.2.1` | `MIT` | `package-lock` |
| `mdast-util-to-markdown` | `2.1.2` | `MIT` | `package-lock` |
| `mdast-util-to-string` | `4.0.0` | `MIT` | `package-lock` |
| `micromark` | `4.0.2` | `MIT` | `package-lock` |
| `micromark-core-commonmark` | `2.0.3` | `MIT` | `package-lock` |
| `micromark-extension-gfm` | `3.0.0` | `MIT` | `package-lock` |
| `micromark-extension-gfm-autolink-literal` | `2.1.0` | `MIT` | `package-lock` |
| `micromark-extension-gfm-footnote` | `2.1.0` | `MIT` | `package-lock` |
| `micromark-extension-gfm-strikethrough` | `2.1.0` | `MIT` | `package-lock` |
| `micromark-extension-gfm-table` | `2.1.1` | `MIT` | `package-lock` |
| `micromark-extension-gfm-tagfilter` | `2.0.0` | `MIT` | `package-lock` |
| `micromark-extension-gfm-task-list-item` | `2.1.0` | `MIT` | `package-lock` |
| `micromark-factory-destination` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-factory-label` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-factory-space` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-factory-title` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-factory-whitespace` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-character` | `2.1.1` | `MIT` | `package-lock` |
| `micromark-util-chunked` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-classify-character` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-combine-extensions` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-decode-numeric-character-reference` | `2.0.2` | `MIT` | `package-lock` |
| `micromark-util-decode-string` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-encode` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-html-tag-name` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-normalize-identifier` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-resolve-all` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-sanitize-uri` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-subtokenize` | `2.1.0` | `MIT` | `package-lock` |
| `micromark-util-symbol` | `2.0.1` | `MIT` | `package-lock` |
| `micromark-util-types` | `2.0.2` | `MIT` | `package-lock` |
| `ms` | `2.1.3` | `MIT` | `package-lock` |
| `nanoid` | `3.3.11` | `MIT` | `package-lock` |
| `next` | `16.2.3` | `MIT` | `package-lock` |
| `next-themes` | `0.4.6` | `MIT` | `package-lock` |
| `parse-entities` | `4.0.2` | `MIT` | `package-lock` |
| `picocolors` | `1.1.1` | `ISC` | `package-lock` |
| `postcss` | `8.4.31` | `MIT` | `package-lock` |
| `postcss` | `8.5.8` | `MIT` | `package-lock` |
| `postcss-selector-parser` | `6.0.10` | `MIT` | `package-lock` |
| `property-information` | `7.1.0` | `MIT` | `package-lock` |
| `radix-ui` | `1.4.3` | `MIT` | `package-lock` |
| `react` | `19.2.4` | `MIT` | `package-lock` |
| `react-dom` | `19.2.4` | `MIT` | `package-lock` |
| `react-markdown` | `10.1.0` | `MIT` | `package-lock` |
| `react-remove-scroll` | `2.7.2` | `MIT` | `package-lock` |
| `react-remove-scroll-bar` | `2.3.8` | `MIT` | `package-lock` |
| `react-style-singleton` | `2.2.3` | `MIT` | `package-lock` |
| `remark-gfm` | `4.0.1` | `MIT` | `package-lock` |
| `remark-parse` | `11.0.0` | `MIT` | `package-lock` |
| `remark-rehype` | `11.1.2` | `MIT` | `package-lock` |
| `remark-stringify` | `11.0.0` | `MIT` | `package-lock` |
| `scheduler` | `0.27.0` | `MIT` | `package-lock` |
| `semver` | `7.7.4` | `ISC` | `package-lock` |
| `sharp` | `0.34.5` | `Apache-2.0` | `package-lock` |
| `source-map-js` | `1.2.1` | `BSD-3-Clause` | `package-lock` |
| `space-separated-tokens` | `2.0.2` | `MIT` | `package-lock` |
| `stringify-entities` | `4.0.4` | `MIT` | `package-lock` |
| `style-to-js` | `1.1.21` | `MIT` | `package-lock` |
| `style-to-object` | `1.0.14` | `MIT` | `package-lock` |
| `styled-jsx` | `5.1.6` | `MIT` | `package-lock` |
| `tailwind-merge` | `3.5.0` | `MIT` | `package-lock` |
| `tailwindcss` | `4.2.2` | `MIT` | `package-lock` |
| `tapable` | `2.3.2` | `MIT` | `package-lock` |
| `trim-lines` | `3.0.1` | `MIT` | `package-lock` |
| `trough` | `2.2.0` | `MIT` | `package-lock` |
| `tslib` | `2.8.1` | `0BSD` | `package-lock` |
| `tslib` | `2.8.1` | `0BSD` | `package-lock` |
| `unified` | `11.0.5` | `MIT` | `package-lock` |
| `unist-util-is` | `6.0.1` | `MIT` | `package-lock` |
| `unist-util-position` | `5.0.0` | `MIT` | `package-lock` |
| `unist-util-stringify-position` | `4.0.0` | `MIT` | `package-lock` |
| `unist-util-visit` | `5.1.0` | `MIT` | `package-lock` |
| `unist-util-visit-parents` | `6.0.2` | `MIT` | `package-lock` |
| `use-callback-ref` | `1.3.3` | `MIT` | `package-lock` |
| `use-sidecar` | `1.1.3` | `MIT` | `package-lock` |
| `use-sync-external-store` | `1.6.0` | `MIT` | `package-lock` |
| `util-deprecate` | `1.0.2` | `MIT` | `package-lock` |
| `vfile` | `6.0.3` | `MIT` | `package-lock` |
| `vfile-message` | `4.0.3` | `MIT` | `package-lock` |
| `zod` | `4.3.6` | `MIT` | `package-lock` |
| `zwitch` | `2.0.4` | `MIT` | `package-lock` |
