#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Generate version from current timestamp or git commit
function generateVersion() {
  // Try to get git commit hash
  try {
    const gitHash = execSync('git rev-parse --short HEAD', { encoding: 'utf8' }).trim();
    const gitBranch = execSync('git rev-parse --abbrev-ref HEAD', { encoding: 'utf8' }).trim();
    return `${gitBranch}-${gitHash}`;
  } catch (error) {
    // Fallback to timestamp if git is not available
    return new Date().toISOString();
  }
}

function updateVersion() {
  const version = generateVersion();
  const buildTime = new Date().toISOString();

  const versionInfo = {
    version,
    buildTime,
  };

  const versionFilePath = path.join(__dirname, '../public/version.json');

  fs.writeFileSync(versionFilePath, JSON.stringify(versionInfo, null, 2));

  console.log('✓ Version file updated:');
  console.log(`  Version: ${version}`);
  console.log(`  Build time: ${buildTime}`);
}

updateVersion();
