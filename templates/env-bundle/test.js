// 离线自测：不需要 jsdom，用一个最小的假窗口。
const assert = require('node:assert');
const { applyEnvBundle, SCHEMA } = require('./apply');

class Navigator {}
Object.defineProperty(Navigator.prototype, 'userAgent', { get() { return 'jsdom'; }, configurable: true });
class Screen {}
class CSSStyleDeclaration {
    constructor() { this.values = {}; }
    getPropertyValue(name) { return this.values[name] || ''; }
    setProperty(name, value) { this.values[name] = String(value); }
}
const win = { navigator: new Navigator(), screen: new Screen(), CSSStyleDeclaration, innerWidth: 1024, document: {} };

const bundle = {
    schema: SCHEMA,
    navigator: {
        userAgent: { type: 'string', value: 'Mozilla/5.0 Test' },
        languages: { type: 'object', value: ['en-US', 'en'] },
        webdriver: { type: 'boolean', value: false },
        geolocation: { type: 'object', value: { __t: 'Geolocation' } },
        connection: { error: 'not supported' },
        plugins: { type: 'object', value: [
            { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format',
              mimeTypes: [{ type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
                          { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' }] },
            { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format',
              mimeTypes: [{ type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
                          { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' }] }] },
        mimeTypes: { type: 'object', value: [
            { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
            { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' }] },
    },
    screen: { width: { type: 'number', value: 1920 }, orientation: { type: 'object', value: { __t: 'Object' } } },
    window: { metrics: { innerWidth: { type: 'number', value: 1512 }, origin: { type: 'string', value: 'x' } },
              globals: [['innerWidth', 'number'], ['WebGLRenderingContext', 'function']] },
    css: { for_in_count: 3, props: ['color'], values: { color: 'rgb(0, 0, 0)' },
           protoEntries: [{ proto: 'CSSStyleProperties', names: [['backgroundColor', true], ['background-color', true], ['cssFloat', true], ['getPropertyValue', false]] }] },
    timing: { timezone: { value: 'Asia/Shanghai' } },
};

const report = applyEnvBundle(win, bundle);
assert.strictEqual(win.navigator.userAgent, 'Mozilla/5.0 Test');
assert.deepStrictEqual([...win.navigator.languages], ['en-US', 'en']);
assert.strictEqual(win.navigator.webdriver, false);
assert.deepStrictEqual(Object.keys(win.navigator), [], '属性在原型上，实例自身没有');
assert.strictEqual(win.navigator.plugins.length, 2);
assert.strictEqual(win.navigator.mimeTypes.length, 2, '同一类型只有一个对象');
assert.strictEqual(win.navigator.plugins.namedItem('Chrome PDF Viewer').item(1), win.navigator.mimeTypes.namedItem('text/pdf'));
assert.strictEqual(win.navigator.mimeTypes.item(0).enabledPlugin.name, 'PDF Viewer');
assert.strictEqual(win.screen.width, 1920);
assert.strictEqual(win.innerWidth, 1512);
const style = new CSSStyleDeclaration();
style.backgroundColor = 'red';
assert.strictEqual(style['background-color'], 'red');
style.cssFloat = 'left';
assert.strictEqual(style.getPropertyValue('float'), 'left');
assert.ok(report.skipped.some((s) => s.startsWith('navigator.geolocation')));
assert.ok(report.skipped.some((s) => s.startsWith('navigator.connection')));
assert.ok(report.skipped.some((s) => s.startsWith('screen.orientation')));
assert.deepStrictEqual(report.missingGlobals, ['WebGLRenderingContext:function']);
assert.ok(report.notes.some((s) => s.includes('TZ=Asia/Shanghai')));
assert.throws(() => applyEnvBundle(win, { schema: 'other' }));
console.log('env-bundle 自测通过');
