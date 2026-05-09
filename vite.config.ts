import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { existsSync } from 'fs';
import { join } from 'path';

import { viteStaticCopy } from 'vite-plugin-static-copy';

const onnxSrc = join('node_modules', 'onnxruntime-web', 'dist', '*.jsep.*');
const hasOnnx = existsSync('node_modules/onnxruntime-web/dist');

export default defineConfig({
	plugins: [
		sveltekit(),
		hasOnnx ? viteStaticCopy({
			targets: [
				{
					src: onnxSrc,
					dest: 'wasm'
				}
			]
		}) : null
	].filter(Boolean),
	define: {
		APP_VERSION: JSON.stringify(process.env.npm_package_version),
		APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || 'dev-build')
	},
	build: {
		sourcemap: true
	},
	worker: {
		format: 'es'
	},
	esbuild: {
		pure: process.env.ENV === 'dev' ? [] : ['console.log', 'console.debug', 'console.error']
	}
});
