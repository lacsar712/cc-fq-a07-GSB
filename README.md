# FASTQ 质控流水线台（FASTQ QC Pipeline Console）

从零实现的全栈演示：上传/选择小型 FASTQ → **Actor 队列流水线**质控 → 查看阶段状态与指标 →
**服务端双作业差分台**（总体状态 / 三指标差值 / 四阶段状态对照，审计员可只读使用）。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11 · FastAPI · SQLAlchemy · PostgreSQL |
| 流水线 | `ParseActor` → `QualityHistActor` → `NContentActor` → `ReportActor`（asyncio.Queue） |
| 前端 | Vue 3 · Vite · Quasar · 中文 UI · nginx `/api` 反代 |
| 基建 | docker compose（db / backend / seed / frontend） |

## 端口

| 服务 | 地址 |
|------|------|
| Frontend | http://localhost:3184 |
| Backend API | http://localhost:8184 |
| PostgreSQL | localhost:54384 |

## 账号

| 用户 | 密码 | 权限 |
|------|------|------|
| `bioops` | `fastq123456` | 可提交质控作业 |
| `auditor` | `audit123456` | 只读结果，不可提交 |

## 一键启动

```bash
cd projects/09-fastq-qc-pipeline
docker compose up --build
```

镜像源：Postgres/Node/Nginx 使用 `docker.m.daocloud.io`；npm 使用 `registry.npmmirror.com`；pip 使用清华源。

启动后 seed 会写入：

- `demo-good-r1`：合格样例（可算出 `mean_quality` / `n_rate`）
- `demo-broken-malformed`：损坏样例（`ParseActor` 失败，后续阶段 skipped）

## Verification（验收）

1. 打开 http://localhost:3184 ，用 `bioops` / `fastq123456` 登录。
2. **样例库** 看到 2 条样例 → 选合格样例 **提交质控作业**。
3. 作业详情页看到四个 Actor 阶段均为成功，指标卡出现 `reads` / `mean_quality` / `n_rate`。
4. 再跑损坏样例：`ParseActor` = failed，其余 = skipped。
5. 进入 **差分台**（导航栏），选第 3 步的成功作业与第 4 步的失败作业，点 **执行差分**：
   - 顶部徽标显示总体状态“不一致”；
   - 三指标差值表中失败侧三项均标 **B 侧缺失 / 无法比较**，行高亮；
   - 四阶段对照表逐行给出 success↔failed、success↔skipped，不一致行高亮；
   - 差值与状态均来自 `POST /api/jobs/diff` 响应，点作业编号进两侧详情页可核对一致。
6. 退出，用 `auditor` / `audit123456` 登录：可看历史、详情与**差分台**，但导航无提交入口、`POST /api/jobs` 返回 403（差分接口是只读接口，不能借此提交新作业）。
7. 健康检查：`curl http://localhost:8184/api/health`

## API

- `POST /api/auth/login`
- `GET  /api/health`
- `GET  /api/samples`
- `POST /api/jobs` `{ "sampleId": 1 }` 或 `{ "fastqText": "..." }`（仅 bioops，auditor 403）
- `GET  /api/jobs`
- `GET  /api/jobs/{id}`
- `GET  /api/jobs/{id}/stages`
- `POST /api/jobs/diff` `{ "baseJobId": 1, "targetJobId": 2 }`（登录可用，含 auditor；只读，不创建作业）

差分响应包含：`status_same`（总体状态是否相同）、`metric_diffs`（reads / mean_quality / n_rate
三项的双方值、服务端计算的 `delta = target - base`、`base_missing` / `target_missing` 缺失标记、
`same` 结论）与 `stage_diffs`（四个 Actor 阶段双方状态对照与 `same`）。**前端只做展示，不在浏览器里
拉两条详情自行减数。**

## 本地单测（可选）

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

覆盖：畸形 FASTQ 在 `ParseActor` 失败；正常样例产出 `mean_quality`。

## 目录结构

```
09-fastq-qc-pipeline/
  PRD.md
  README.md
  docker-compose.yml
  backend/
    Dockerfile
    seed.py
    data/{good,broken}.fastq
    app/
      main.py api.py auth.py models.py schemas.py diff.py
      pipeline/{actors,runner}.py
    tests/{test_actors,test_diff}.py
  frontend/
    Dockerfile nginx.conf
    src/pages/{Login,Samples,JobSubmit,JobDetail,JobHistory,JobDiff}Page.vue
```
