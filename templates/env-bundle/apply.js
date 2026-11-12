'use strict';
/**
 * 把 camoufox-reverse-mcp 的环境包（compare_env(output_path=...) 导出，
 * schema camoufox-reverse-mcp/env-bundle@1）套到 jsdom 的 window，或 vm 沙箱里
 * 充当 window 的对象上。
 *
 * 只套用包里真实采到的值，不编造；返回一份报告，列出套用了什么、跳过了什么。
 * canvas 像素、WebGL 绘制和音频渲染不在这里伪造：先用插桩日志确认目标实际读了
 * 哪些值，再针对性补。
 */

const SCHEMA = 'camoufox-reverse-mcp/env-bundle@1';

// 包里的值：原始值、数组、{__t:'undefined'}，其余对象只记了类型名 {__t:'<Tag>'}。
function plainValue(v) {
    if (v === null || typeof v !== 'object') return { ok: true, value: v };
    if (Array.isArray(v)) {
        const out = [];
        for (const item of v) {
            const r = plainValue(item);
            if (!r.ok) return r;
            out.push(r.value);
        }
        return { ok: true, value: Object.freeze(out) };
    }
    if (v.__t === 'undefined') return { ok: true, value: undefined };
    return { ok: false, reason: `只记了类型 ${v.__t || 'object'}，没有值` };
}

function defineGetter(target, name, value, enumerable = true) {
    Object.defineProperty(target, name, { get() { return value; }, configurable: true, enumerable });
}

// 浏览器里 navigator/screen 的属性是原型上的 getter，实例自身没有属性。
function protoOf(obj) {
    const proto = obj && Object.getPrototypeOf(obj);
    return proto && proto !== Object.prototype ? proto : obj;
}

function applyGetters(target, entries, report, section, skip) {
    for (const [name, entry] of Object.entries(entries || {})) {
        if (skip && skip.has(name)) continue;
        if (!entry || 'error' in entry) {
            report.skipped.push(`${section}.${name}：采集时出错（${entry ? entry.error : '缺失'}）`);
            continue;
        }
        const r = plainValue(entry.value);
        if (!r.ok) {
            report.skipped.push(`${section}.${name}：${r.reason}`);
            continue;
        }
        try {
            defineGetter(target, name, r.value);
            report.applied.push(`${section}.${name}`);
        } catch (e) {
            report.skipped.push(`${section}.${name}：定义失败（${e.message}）`);
        }
    }
}

// 最小的 PluginArray / MimeTypeArray：下标、length、item()、namedItem() 和迭代。
function pluginLikeArray(items, nameKey) {
    const arr = {};
    items.forEach((item, i) => { arr[i] = item; });
    Object.defineProperties(arr, {
        length: { value: items.length },
        item: { value: (i) => items[i] || null },
        namedItem: { value: (n) => items.find((x) => x[nameKey] === n) || null },
        [Symbol.iterator]: { value: function* () { yield* items; } },
    });
    return arr;
}

// 浏览器里同一个 MIME 类型只有一个对象：navigator.mimeTypes 和各插件里的条目共用它。
function buildPlugins(pluginList, mimeList) {
    const byType = new Map();
    const order = Array.isArray(mimeList) && mimeList.length ? mimeList
        : pluginList.flatMap((p) => p.mimeTypes || []);
    for (const m of order) {
        if (!byType.has(m.type)) byType.set(m.type, { type: m.type, suffixes: m.suffixes, description: m.description, enabledPlugin: null });
    }
    const plugins = pluginList.map((p) => {
        const plugin = { name: p.name, filename: p.filename, description: p.description };
        const own = (p.mimeTypes || []).map((m) => {
            if (!byType.has(m.type)) byType.set(m.type, { type: m.type, suffixes: m.suffixes, description: m.description, enabledPlugin: null });
            const mime = byType.get(m.type);
            if (!mime.enabledPlugin) mime.enabledPlugin = plugin;
            return mime;
        });
        Object.defineProperties(plugin, Object.getOwnPropertyDescriptors(pluginLikeArray(own, 'type')));
        return plugin;
    });
    const mimeTypes = order.length ? [...new Set(order.map((m) => byType.get(m.type)))] : [...byType.values()];
    return { plugins: pluginLikeArray(plugins, 'name'), mimeTypes: pluginLikeArray(mimeTypes, 'type') };
}

// CSS 声明原型上的属性名：camelCase、带连字符和 webkit 前缀的都有。
function cssPropertyName(name) {
    if (name === 'cssFloat') return 'float';
    return name.includes('-') ? name : name.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase());
}

function applyCss(win, css, report) {
    const Decl = win.CSSStyleDeclaration;
    if (!Decl || !Array.isArray(css.protoEntries) || !css.protoEntries.length) {
        report.skipped.push('css：窗口里没有 CSSStyleDeclaration，或包里没有原型名');
        return;
    }
    const proto = Decl.prototype;
    const first = css.protoEntries[0];
    let added = 0;
    for (const [name, enumerable] of first.names) {
        if (name in proto) continue;
        const prop = cssPropertyName(name);
        Object.defineProperty(proto, name, {
            get() { return this.getPropertyValue(prop); },
            set(v) { this.setProperty(prop, v); },
            configurable: true,
            enumerable: !!enumerable,
        });
        added++;
    }
    report.applied.push(`css：在 CSSStyleDeclaration.prototype 上补了 ${added} 个属性名（来自 ${first.proto}）`);
    let here = null;
    try {
        if (win.document && typeof win.document.createElement === 'function') {
            here = 0;
            for (const k in win.document.createElement('div').style) here++;  // eslint-disable-line no-unused-vars
        }
    } catch (e) { here = null; }
    report.notes.push(`css：浏览器里 for...in 一个 style 得到 ${css.for_in_count} 个名字` +
        (here === null ? '' : `，这个窗口是 ${here} 个（多出来的去不掉，目标数这个值时要单独处理）`) +
        `；getComputedStyle 有 ${(css.props || []).length} 个属性，值在 bundle.css.values，按目标实际读到的补`);
}

function applyEnvBundle(win, bundle, options = {}) {
    if (!bundle || bundle.schema !== SCHEMA) {
        throw new Error(`不是 ${SCHEMA} 格式的环境包`);
    }
    const report = { applied: [], skipped: [], notes: [] };
    if (bundle.navigator && win.navigator) {
        const target = protoOf(win.navigator);
        applyGetters(target, bundle.navigator, report, 'navigator', new Set(['plugins', 'mimeTypes']));
        const plugins = bundle.navigator.plugins && bundle.navigator.plugins.value;
        if (Array.isArray(plugins)) {
            const built = buildPlugins(plugins, bundle.navigator.mimeTypes && bundle.navigator.mimeTypes.value);
            defineGetter(target, 'plugins', built.plugins);
            defineGetter(target, 'mimeTypes', built.mimeTypes);
            report.applied.push(`navigator.plugins（${plugins.length} 个）与 mimeTypes（${built.mimeTypes.length} 个）`);
        }
    }
    if (bundle.screen && win.screen) {
        applyGetters(protoOf(win.screen), bundle.screen, report, 'screen');
    }
    if (bundle.window && bundle.window.metrics) {
        applyGetters(win, bundle.window.metrics, report, 'window', new Set(['origin', 'isSecureContext', 'crossOriginIsolated']));
        if (Array.isArray(bundle.window.globals)) {
            const missing = bundle.window.globals.filter(([name]) => !(name in win)).map(([name, type]) => `${name}:${type}`);
            report.notes.push(`window：浏览器有 ${bundle.window.globals.length} 个全局名，这个窗口缺 ${missing.length} 个，按目标实际检查的补（见 report.missingGlobals）`);
            report.missingGlobals = missing;
        }
    }
    if (bundle.css) applyCss(win, bundle.css, report);
    const tz = bundle.timing && bundle.timing.timezone && bundle.timing.timezone.value;
    if (tz) report.notes.push(`时区：进程内改不了，启动 Node 时设置 TZ=${tz}`);
    if (bundle.webgl) report.notes.push(`webgl：${bundle.webgl.unmasked_renderer || bundle.webgl.renderer || '未知'}，${bundle.webgl.extension_count || 0} 个扩展；参数在 bundle.webgl.parameters，不在这里伪造`);
    if (bundle.canvas) report.notes.push(`canvas：参照图的 toDataURL 长 ${bundle.canvas.data_url_length}；目标自己画的内容不同，不能直接拿来当返回值`);
    if (bundle.storage) report.notes.push('storage：包里只有键名和值长度，没有值');
    if (bundle.iframe && Array.isArray(bundle.iframe.differs_from_top) && bundle.iframe.differs_from_top.length) {
        report.notes.push(`iframe：这些项和顶层不同：${bundle.iframe.differs_from_top.join('、')}`);
    }
    if (options.verbose) console.log(JSON.stringify(report, null, 2));
    return report;
}

module.exports = { applyEnvBundle, SCHEMA };
