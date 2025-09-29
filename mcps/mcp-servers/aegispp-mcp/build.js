#!/usr/bin/env node

import { execSync } from 'child_process';
import fs from 'fs';

// Create a lenient tsconfig for building
const laxConfig = {
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "rootDir": "src",
    "outDir": "dist",
    "strict": false,
    "noImplicitAny": false,
    "strictNullChecks": false,
    "noImplicitReturns": false,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "exactOptionalPropertyTypes": false,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "skipLibCheck": true,
    "declaration": false,
    "sourceMap": false
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"],
  "ts-node": {
    "esm": true
  }
};

// Write temporary config
fs.writeFileSync('tsconfig.build.json', JSON.stringify(laxConfig, null, 2));

try {
  // Build with lenient config
  execSync('npx tsc -p tsconfig.build.json', { stdio: 'inherit' });
  console.log('✅ Build completed successfully');

  // Fix import extensions in built files
  console.log('🔧 Fixing import extensions...');
  execSync(`find dist -name "*.js" -exec sed -i "s/from '\\(\\.[^']*\\)'/from '\\1.js'/g" {} +`, { stdio: 'inherit' });

  console.log('✅ Aegis++ MCP build complete');
} catch (error) {
  console.error('❌ Build failed:', error.message);
  process.exit(1);
} finally {
  // Cleanup
  fs.unlinkSync('tsconfig.build.json');
}