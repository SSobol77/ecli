<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: src/ecli/extensions/THIRD_PARTY_NOTICES.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Third-Party Notices — ECLI Extensions Layer

`src/ecli/extensions/` is a **curated runtime asset bundle**. It is not a
vendored copy of full VS Code extension repositories. It contains:

- `ecli_integration/` — ECLI-owned Python adapter code (GPL-2.0-only, part of
  ECLI; not third-party);
- `lang/` — imported language/runtime declarative extension assets;
- `themes/` — imported colour-theme declarative extension assets.

## Scope of use

ECLI consumes **only declarative, data-only assets** from the imported folders:

- `package.json` `contributes` metadata (languages, grammars, snippets, themes,
  language configuration);
- TextMate grammars (`syntaxes/*.tmLanguage`, `syntaxes/*.tmLanguage.json`);
- colour themes (`themes/*.json`);
- snippets (`snippets/*.code-snippets`);
- language-configuration metadata (`*language-configuration*.json`);
- localization string tables (`package.nls*.json`).

ECLI does **not** execute any VS Code extension runtime code. There is no VS Code
extension host, no Node.js/TypeScript activation, no `activationEvents`
execution, no `package.json` `scripts`, and no Copilot or language-server
runtime. All imported files are treated as inert data and are read-only from the
ECLI integration perspective; they are not modified to change behavior.

## Microsoft Visual Studio Code — built-in extensions (MIT License)

The declarative assets retained under `lang/` and `themes/` are derived from the
built-in extensions of **Microsoft Visual Studio Code**
(<https://github.com/microsoft/vscode>), distributed under the MIT License.

> Copyright (c) Microsoft Corporation. All rights reserved.
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Upstream TextMate grammars

Several TextMate grammars shipped inside VS Code's built-in extensions originate
from third-party projects (for example MagicPython, and language-specific
community grammars) under their own permissive licenses. Their provenance is
recorded upstream in the per-extension `cgmanifest.json` component-governance
manifests in the Microsoft Visual Studio Code repository. ECLI retains these
grammars unmodified as inert data and does not relicense them; the upstream
provenance and license terms continue to apply to each grammar file.

## ECLI

ECLI itself, including the `ecli_integration/` adapter code, is licensed under
the GNU General Public License version 2 only. See the `LICENSE` file in the
project root.
