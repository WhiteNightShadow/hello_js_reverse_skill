# 工作流选择

主流程见 [问题路由](problem-routing.md)：先定义成功层级，再按现象定位失败层，选依赖最少且能成立的路线，用对照实验收口。

1. 先读已有需求代码和基线，明确数据字段、分页方式、鉴权和最终运行环境。
2. 接口无自定义签名时，直接使用协议采集器，见 [general-collection.md](general-collection.md)。
3. 有签名或动态参数时，先判断是否需要计算，见 [链路 A](problem-routing.md#链路-a这个参数到底要不要算)。
4. 确需生成时，按 [路线阶梯](problem-routing.md#路线阶梯) 选 `templates/node-request`、`templates/python-request`、`templates/vm-sandbox`、`templates/wasm-loader` 或原始 SDK 运行。
5. 默认交付无浏览器依赖的协议程序。用户明确要求页面自动化时才使用 `templates/browser-auto`，并声明浏览器依赖；该模板使用 Chrome，不是 Camoufox。
6. 每次改版从最后成功基线回归，见 [参数跟踪](version-tracking.md)。无法验证的部分保存证据与限制，不把猜测或短时通过宣称为长期稳定。
