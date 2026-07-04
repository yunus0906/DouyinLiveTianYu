# 直播数据分析 Dashboard

这是一个可部署到 Netlify 的纯前端静态项目。数据库 `live.db` 不会上传到任何服务器，SQLite 解析完全在浏览器本地完成。

## 本地运行

```bash
python -m http.server 8000
```

打开：

```text
http://localhost:8000
```

## Netlify 部署

如果从仓库根目录部署，仓库根目录的 `netlify.toml` 已配置：

```toml
[build]
  publish = "live-dashboard"
  command = ""
```

Netlify 配置项：

- Build command：留空
- Publish directory：`live-dashboard`
- Node.js：不需要
- 后端服务：不需要

## 注意事项

- `libs/sql-wasm.wasm` 已配置 `Content-Type: application/wasm`。
- 所有第三方依赖都在 `libs/` 本地目录内，不依赖 CDN。
- 页面只读取用户本地选择的 SQLite 文件，不会修改数据库内容。
