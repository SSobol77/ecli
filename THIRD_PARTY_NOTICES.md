# Third-Party Notices

ECLI is licensed under the GNU General Public License version 2 only
(GPL-2.0-only). This file records third-party works whose **concepts or
architecture** influenced ECLI, or whose assets ECLI redistributes, together
with their licenses and attribution.

ECLI does not bundle or execute any third-party runtime listed here unless
explicitly stated.

---

## fnando/vscode-linter (provider-framework concept) — MIT License

- Project: `fnando/vscode-linter`
- Repository: https://github.com/fnando/vscode-linter
- License: MIT License

ECLI's F4 Diagnostics / Linter framework (issue #104, under
`src/ecli/extensions/ecli_integration/diagnostics/`) **ports the provider-
framework concept** of this project to Python:

- the idea of a provider/linter **registry** with per-tool **metadata**,
- a **command contract** (a tool + a fixed argv) and a
  **stdout → normalized offenses (diagnostics)** parser shape,
- documentation/capability metadata such as a documentation URL and rule code.

What ECLI **does not** do:

- ECLI does **not** vendor or execute any code from `fnando/vscode-linter`.
- ECLI does **not** run a VS Code extension host, Node activation,
  `package.json` scripts, `activationEvents`, or a Copilot runtime.
- ECLI does **not** copy the project's source files; it re-implements the
  concept independently in Python.
- ECLI ships **no custom lint rules or linting engines**. Every provider wraps an
  existing, professional external tool through a safe ECLI-owned adapter; only
  Ruff is active today, and the remaining providers are roadmap metadata in the
  registry.

The MIT License requires preservation of its copyright and permission notice
when source is used materially. ECLI uses the architectural concept rather than
the source; this notice is provided for attribution and good-faith transparency.

```
MIT License

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
```
