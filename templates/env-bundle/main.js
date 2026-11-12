// Offline test dispatch must precede dependency loading and business work.
if (process.argv.includes('--test')) {
    const result = require('node:child_process').spawnSync(process.execPath,
        [require('node:path').join(__dirname, 'test.js')], {stdio: 'inherit'});
    process.exitCode = result.status ?? 1;
} else {
/**
 * 把 compare_env(output_path=...) 导出的环境包套到 jsdom 上，打印套用报告。
 *
 *   npm install            # 装 jsdom
 *   node main.js env.json https://target.example/
 *
 * 在自己的补环境代码里直接用 apply.js：
 *   const { applyEnvBundle } = require('./apply');
 *   const report = applyEnvBundle(dom.window, bundle);
 */
const fs = require('node:fs');
const { applyEnvBundle } = require('./apply');

const [bundlePath, url = 'https://example.com/'] = process.argv.slice(2);
if (!bundlePath) {
    console.error('用法：node main.js <env.json> [页面地址]');
    process.exitCode = 2;
} else {
    const { JSDOM } = require('jsdom');
    const bundle = JSON.parse(fs.readFileSync(bundlePath, 'utf8'));
    const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', { url, pretendToBeVisual: true });
    const report = applyEnvBundle(dom.window, bundle);
    console.log(JSON.stringify(report, null, 2));
    console.log('navigator.userAgent =', dom.window.navigator.userAgent);
}
}
