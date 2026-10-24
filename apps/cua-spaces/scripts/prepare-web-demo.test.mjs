// @vitest-environment node
// SPDX-License-Identifier: FSL-1.1-MIT
// Copyright (c) 2026 Cua AI, Inc.

import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { prepareWebDemo } from './prepare-web-demo.mjs';

describe('static browser example packaging', () => {
  let app;
  const html = '<script type="module" src="/assets/main.js"></script>';
  const wasm = new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0]);

  beforeEach(() => {
    app = mkdtempSync(join(tmpdir(), 'cua-web-demo-'));
    mkdirSync(join(app, 'dist', 'assets'), { recursive: true });
    writeFileSync(join(app, 'dist', 'index.html'), html);
    writeFileSync(join(app, 'dist', 'assets', 'main.js'), 'export default 1;');
    writeFileSync(join(app, 'dist', 'assets', 'core.wasm'), wasm);
    writeFileSync(
      join(app, 'web-demo.html'),
      "<iframe src='/app/index.html?surface=main'></iframe>"
    );
    writeFileSync(join(app, 'LICENSE'), 'FSL-1.1-MIT');
  });

  afterEach(() => rmSync(app, { recursive: true, force: true }));

  it('keeps app asset URLs valid and copies binary assets and the license', () => {
    const out = prepareWebDemo(app);
    expect(readFileSync(join(out, 'app', 'index.html'), 'utf8')).toBe(html);
    expect(readFileSync(join(out, 'assets', 'main.js'), 'utf8')).toBe('export default 1;');
    expect(new Uint8Array(readFileSync(join(out, 'assets', 'core.wasm')))).toEqual(wasm);
    expect(readFileSync(join(out, 'LICENSE.txt'), 'utf8')).toBe('FSL-1.1-MIT');
    expect(readFileSync(join(out, 'index.html'), 'utf8')).toContain('surface=main');
  });

  it('does not copy private state or arbitrary app and dist files', () => {
    mkdirSync(join(app, '.herenow'));
    writeFileSync(join(app, '.herenow', 'state.json'), 'private publish state');
    writeFileSync(join(app, '.env'), 'PRIVATE_PLACEHOLDER=test-only');
    writeFileSync(join(app, 'dist', '.env'), 'PRIVATE_PLACEHOLDER=test-only');
    expect(readdirSync(prepareWebDemo(app)).sort()).toEqual([
      'LICENSE.txt',
      'app',
      'assets',
      'index.html',
    ]);
  });

  it('replaces stale output rather than leaving old deployable files', () => {
    const out = prepareWebDemo(app);
    writeFileSync(join(out, 'assets', 'stale.js'), 'old');
    writeFileSync(join(out, 'private.txt'), 'stale output');
    prepareWebDemo(app);
    expect(readdirSync(join(out, 'assets')).sort()).toEqual(['core.wasm', 'main.js']);
    expect(readdirSync(out).sort()).toEqual(['LICENSE.txt', 'app', 'assets', 'index.html']);
  });

  it.each(['index.html', 'assets'])('refuses an incomplete build missing %s', (name) => {
    rmSync(join(app, 'dist', name), { recursive: true, force: true });
    expect(() => prepareWebDemo(app)).toThrow(`Missing dist/${name}; run pnpm build first.`);
  });

  it('refuses symlinked build inputs instead of publishing their targets', () => {
    const outside = join(app, 'private.txt');
    writeFileSync(outside, 'private data');
    symlinkSync(outside, join(app, 'dist', 'assets', 'linked.txt'));
    expect(() => prepareWebDemo(app)).toThrow('Web demo inputs must not contain symbolic links.');
  });
});
