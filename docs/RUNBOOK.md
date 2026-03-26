# 🟢 智树 (TreeEdu) V1.0 后端与前端服务运行手册 (RUNBOOK)

这份文档旨在指导开发者或用户如何在本地从零启动并测试整个 **TreeEdu V1.0** 闭环系统。我们提供两种启动方式：**原生本地开发环境运行** 以及 **Docker 一键容器化运行**。

---

## 方式一：Docker 一键部署 (推荐 🚀)

系统已经在根目录配置了完善的 `docker-compose.yml` 及其对应的跨端 `Dockerfile`。

### 1. 准备环境变量
在 `backend/` 目录下，确保 `.env` 文件正常填充（系统默认已带 `.env.example`）：
```ini
DATABASE_URL=sqlite+aiosqlite:///./treeedu.db
ALIYUN_API_KEY=sk-xxxxxx # 你的 通义千问 API Key
```

### 2. 启动容器
进入工程**根目录** `d:/project/python/jiaoyu_agent`，在终端输入：
```bash
docker-compose up -d --build
```
*这将会：*
1. 自动构建前端（包含 `npm run build` 打包及 `nginx` 配置）。
2. 构建后端（Python 3.10、依赖安装及 Uvicorn 异步启动）。

### 3. 本地访问与测试
* **C 端学生门户 (Frontend)**：打开浏览器访问 👉 `http://localhost:80` 或 `http://localhost:5173`。
* **API 接口 (Backend)**：FastAPI 服务位于 👉 `http://localhost:8000/docs`（可在此查看 Swagger 文档）。
* *Tips: Nginx 会自动把所有 `/api/*` 开头的请求反向代理到 8000 端口，前端代码无须处理 CORS 跨域问题。*

---

## 方式二：原生本地开发联调 (Dev Mode 🛠️)

如果你需要修改代码并查看控制台实时报错，推荐将前端和后端分别打开终端运行。

### 1. 运行后端 (FastAPI)
打开第一个终端，进入 `backend` 文件夹：
```bash
cd backend

# 1. 激活虚拟环境 (需预先运行 python -m venv venv)
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 2. 确保依赖已安装
pip install -r requirements.txt

# 3. 首次运行前建议确保有 SQLite DB 数据 (自动挂载)
# 4. 启动服务 (启用热重载)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
后端终端将显示 `Application startup complete`。

### 2. 运行前端 (Vite)
打开第二个终端，进入 `frontend` 文件夹：
```bash
cd frontend

# 1. 安装前端 Node 依赖包
npm install

# 2. 启动 Vite 热重载测试服务器
npm run dev
```
按照终端提示，通常在浏览器打开 👉 `http://localhost:5173`。
此时前端网络请求会被 `vite.config.ts` 中的 proxy 自动代理至后端的 8000 端口。

---

## ✅ 极速测试数据建议 (Mock Fallback)

1. **账户登录**
   可以随便输入一个不为空的手机号与密码即可登录，系统目前未强制挂载外部短信通道。
2. **教材挂载 & Mock 数据**
   - 为了防备 PageIndex API 每日限额导致的接口拦截，我们在 `backend/scripts/` 中预留了 `add_test_material.py` 等脚本，用于手工给 SQLite 注入真实的教辅大纲（如《语文一年级》）。
   - 用户登入后，可以在顶部点击**“书架”**，并直接验证图谱、加入学习舱对话或进行全量诊断。
3. **功能验收点：**
   * **动态学习舱：** 开始学习后，请尝试与模型 Tutor 聊天指正，验证 SSE 打字机效果与数学公式渲染。
   * **知识书林 ECharts：** 查看知识树彩色（绿/黄/红锁）分布情况。
   * **学习计划与家长周报：** 点击左侧导航，观察 LangGraph 是否在后台自动运算并产出结果。
   * **错题诊断：** 参与摸底诊断，故意做错几道题，然后查看错题本中是否真实生成了复习记录及其变式。

---

## 单元测试 (避免浪费 Token)

### pageindex 模块测试

修改 `pageindex` 相关代码后（尤其是 `generate_toc_continue`、`generate_toc_init`、`extract_json` 等），应先运行单元测试验证逻辑正确性，避免真实 API 调用浪费 token。

```bash
cd backend
python -m pytest tests/test_page_index.py -v
```

测试文件位于 `backend/tests/test_page_index.py`，覆盖以下场景：

| 测试用例 | 验证内容 |
|---------|---------|
| `test_valid_json` | 完整 JSON 正确解析 |
| `test_json_with_code_block` | 带 markdown 代码块的 JSON 正确提取 |
| `test_incomplete_json_returns_empty_dict` | 无效 JSON 返回 `{}` 而非抛异常 |
| `test_finish_reason_finished_valid_json` | API 返回 `finished` 且 JSON 完整时直接返回 |
| `test_api_error_raises` | API 返回 Error 时正确抛异常 |
| `test_unexpected_finish_reason_raises` | 非预期 finish_reason 时抛异常 |
| `test_max_retries_exceeded_raises` | 重试 5 次后仍失败时抛异常 |

**关键修复说明：**

- `extract_json` 失败时返回 `{}` 而非抛 `JSONDecodeError`，因此 `generate_toc_continue` 的重试逻辑需要检查返回值是否为非空 list/dict，不能仅依赖异常捕获。
- 通义千问 API 的 `max_tokens` 上限为 **8192**，设置过大会导致 `400 Bad Request`。

