#!/usr/bin/env node
// SPDX-License-Identifier: FSL-1.1-MIT
// Copyright (c) 2026 Cua AI, Inc.

import { cpSync, existsSync, lstatSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const app = resolve(dirname(fileURLToPath(import.meta.url)), '..');

export function prepareWebDemo(appDir = app) {
  const dist = join(appDir, 'dist');
  for (const name of ['index.html', 'assets']) {
    if (!existsSync(join(dist, name))) {
      throw new Error(`Missing dist/${name}; run pnpm build first.`);
    }
  }

  const out = join(appDir, 'web-dist');
  rmSync(out, { recursive: true, force: true });
  mkdirSync(join(out, 'app'), { recursive: true });
  const copy = (source, destination) =>
    cpSync(source, destination, {
      recursive: true,
      filter(path) {
        if (lstatSync(path).isSymbolicLink()) {
          throw new Error('Web demo inputs must not contain symbolic links.');
        }
        return true;
      },
    });
  copy(join(dist, 'assets'), join(out, 'assets'));
  copy(join(dist, 'index.html'), join(out, 'app', 'index.html'));
  copy(join(appDir, 'web-demo.html'), join(out, 'index.html'));
  copy(join(appDir, 'LICENSE'), join(out, 'LICENSE.txt'));
  return out;
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  console.log(`Browser example ready: ${prepareWebDemo()}`);
}
