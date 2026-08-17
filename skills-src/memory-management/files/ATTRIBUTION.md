# Attribution

This skill is adapted from **claude-memory-manager** by jau123:

- Upstream: https://github.com/jau123/claude-memory-manager
- Snapshot: commit `c766942`
- License: MIT (Copyright (c) 2026 jau123)

The discipline core (typed schema, locality routing, index-budget rules) and
the audit-check design derive from the upstream SKILL.md, references, and
`templates/audit-memory.template.sh`. This port re-schemas the write spec to
the house 4-type / nested-metadata convention, translates the content to
English, and (in the Claude package) replaces the bash audit template with a
stdlib-Python rewrite.

## Upstream license (MIT)

Copyright (c) 2026 jau123

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
