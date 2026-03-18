# 示例：某网站请求签名逆向分析

> 这是一个虚拟的分析示例，展示完整的逆向分析流程。

## Phase 1：目标侦察

### 目标信息

- **网站**: https://example.com/data
- **目标**: 采集商品列表数据
- **接口**: `GET /api/v1/products?page=1&sign=xxx&t=1710000000`

### 网络请求分析

使用 MCP 工具捕获请求：

```
[js-reverse] list_network_requests(resourceTypes=["XHR"])
→ 发现数据接口: /api/v1/products

[js-reverse] get_network_request(reqid=42)
→ 获取完整请求信息
```

**请求详情**:
```
URL: https://example.com/api/v1/products?page=1&sign=a1b2c3d4e5f6...&t=1710000000
Method: GET
Headers:
  Cookie: session=abc123; token=xyz789
  X-Request-Id: 9f8e7d6c
```

**加密参数分析**:
| 参数 | 示例值 | 长度 | 字符集 | 初步判断 |
|------|--------|------|--------|---------|
| sign | a1b2c3d4e5f67890... | 32 | hex | MD5 |
| t | 1710000000 | 10 | 数字 | 时间戳(秒) |

## Phase 2：静态分析

### 搜索加密入口

```
[js-reverse] search_in_sources(query="sign=")
→ 在 /static/js/app.js 第 1234 行找到: params.sign = generateSign(page, timestamp)

[js-reverse] search_in_sources(query="generateSign")
→ 在 /static/js/utils.js 第 567 行找到函数定义
```

### 读取关键代码

```
[js-reverse] get_script_source(url="https://example.com/static/js/utils.js", startLine=560, endLine=590)
```

还原后的关键代码：
```javascript
function generateSign(page, timestamp) {
    var SECRET = 'my_secret_key_2024';
    var raw = page + '|' + timestamp + '|' + SECRET;
    return md5(raw);
}
```

## Phase 3：动态验证

### 注入 Hook 验证

```
[js-reverse] inject_before_load(script="XHR Hook + generateSign Hook")
[js-reverse] navigate_page(type="reload")
[js-reverse] list_console_messages()
```

Hook 输出：
```
[Hook:Custom] generateSign 调用
[Hook:Custom] 参数: [1, 1710000000]
[Hook:Custom] 返回: "e10adc3949ba59abbe56e057f20f883e"
```

### 验证 MD5

```javascript
const crypto = require('crypto');
const raw = '1|1710000000|my_secret_key_2024';
const sign = crypto.createHash('md5').update(raw).digest('hex');
console.log(sign); // e10adc3949ba59abbe56e057f20f883e ✓ 匹配！
```

## Phase 4：Node.js 还原

选择 **模式A：纯 Node.js 算法还原**。

### 加密函数

```javascript
const crypto = require('crypto');

const SECRET = 'my_secret_key_2024';

function generateSign(page, timestamp) {
    const raw = `${page}|${timestamp}|${SECRET}`;
    return crypto.createHash('md5').update(raw).digest('hex');
}
```

### 请求脚本

```javascript
async function fetchPage(page) {
    const t = Math.floor(Date.now() / 1000);
    const sign = generateSign(page, t);
    
    const response = await axios.get('https://example.com/api/v1/products', {
        params: { page, sign, t },
        headers: {
            Cookie: 'session=abc123',
            'User-Agent': 'Mozilla/5.0 ...',
        },
    });
    
    return response.data;
}
```

## Phase 5：验证

运行结果：
```
[*] 项目：商品数据采集
[+] 正在采集第 1/5 页... ✓ 获取 20 条数据
[+] 正在采集第 2/5 页... ✓ 获取 20 条数据
[+] 正在采集第 3/5 页... ✓ 获取 20 条数据
[+] 正在采集第 4/5 页... ✓ 获取 20 条数据
[+] 正在采集第 5/5 页... ✓ 获取 20 条数据
[+] 采集完成，共 100 条数据

============================== 计算结果 ==============================
答案：125890
======================================================================
```

## 涉及的逆向技能点

1. Network 抓包分析
2. JS 源码搜索定位
3. MD5 签名还原
4. XHR Hook 验证
5. Node.js 纯算法模拟请求
