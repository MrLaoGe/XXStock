# X2Stock - A股 Agent + 量化投资数据平台

## 项目简介
X2Stock 是一个面向A股投资者的综合数据平台，整合行情、新闻、公告、AI 分析报告与量化回测功能，帮助投资者产出专业投资分析与市场风向判断。

## Skill 插件

Skill 是独立版本化的研究能力包。平台以 x2stock.skill.v1 JSON 协议向子进程传入参数、授权数据集和数据来源；Skill 从标准输入读取一个 JSON 对象，向标准输出返回一个 JSON 对象，诊断信息写入标准错误。Manifest 声明 Python 版本范围、入口、依赖、权限能力以及输入和输出 JSON Schema。

首个示例包位于 skill_packages/low_valuation_screener。运行 python scripts/package_example_skill.py 会生成可上传的 skill_packages/low-valuation-screener-1.0.0.zip（manifest.json 位于 ZIP 根目录）。然后在“Skills”页面安装。运行结果提供估值排名、数据记录 ID、数据日期、缺失数据、假设和风险提示。

### 配置与运行

在后端环境变量或 backend/.env 中配置 X2STOCK_ADMIN_KEY，再启动平台。Skills 页面要求输入该密钥；密钥只保存在当前浏览器会话中。未配置密钥时安装、启停、卸载和运行操作会被禁用。建议设置足够长的随机值，并仅在可信内网使用管理页面。

Skill 运行数据目录由 SKILLS_DIR 指定。Docker Compose 默认保存到 /app/data/skills，该路径位于持久化数据卷内。每个 Skill 的每个版本使用独立源码目录和 Python 虚拟环境。安装通过后台任务执行，可在页面查看状态；安装失败不会替换当前已启用版本。升级成功后旧版本文件保留到卸载该 Skill 时清理。

当前支持权限能力 market.daily_basic.read 和 market.stocks.read。宿主仅提供 Manifest 声明的数据。权限声明不是操作系统沙箱：Skill 是用户信任的 Python 代码，具有后端进程账户的系统权限；不要安装不可信 ZIP。首版只接受本机上传的 ZIP，不支持 URL 或在线商店。

主要接口：

- GET /api/skills：查看已安装 Skill。
- POST /api/skills/install：使用 X-Admin-Key 上传 ZIP，返回后台安装任务 ID。
- GET /api/skills/install/{job_id}：查看安装进度。
- POST /api/skills/{skill_id}/enable|disable、DELETE /api/skills/{skill_id}：管理安装状态。
- POST /api/skills/{skill_id}/run：使用 JSON 参数运行 Skill。
- GET /api/skills/{skill_id}/runs：查看最近运行记录。

### 本地检查

在 backend 目录执行 python -m pytest tests。
