# FASTQ 质控流水线台（FASTQ QC Pipeline Console）

从零实现的全栈演示：上传/选择小型 FASTQ → **Actor 队列流水线**质控 → 查看阶段状态与指标。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11 · FastAPI · SQLAlchemy · PostgreSQL |
| 流水线 | `ParseActor` → `QualityHistActor` → `NContentActor` → `ReportActor`（asyncio.Queue） |
| 差分 | **服务端** `GET /api/jobs/diff`：状态判定 / 三指标差值 / 四阶段对照均在后端计算 |
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
5. 退出，用 `auditor` / `audit123456` 登录：可看历史与详情、**可使用作业差分**，提交作业接口返回 403 / 前端无提交入口。
6. **双作业差分（核心验收）**：在「历史」勾选一条成功与一条失败作业（最多 2 条）→ 点「差分选中」，或进入「作业差分」页分别选择 A/B。页面顶部给出状态是否相同，三指标表给出 `reads` / `mean_quality` / `n_rate` 的 A−B 差值，四阶段表给出 `ParseActor / QualityHistActor / NContentActor / ReportActor` 的状态对照，不一致行红底高亮；失败侧无指标的项以橙色「B 侧缺失」标出，不伪造差值。所有差值与对照均来自差分接口，并与两侧详情页一致。
7. 健康检查：`curl http://localhost:8184/api/health`

## API

- `POST /api/auth/login`
- `GET  /api/health`
- `GET  /api/samples`
- `POST /api/jobs` `{ "sampleId": 1 }` 或 `{ "fastqText": "..." }`（仅 bioops）
- `GET  /api/jobs`
- `GET  /api/jobs/diff?a={id}&b={id}` **服务端差分**：bioops 与 auditor 均可，只读；返回 `status_equal` / `all_equal`、三指标（含 `value_a`/`value_b`/`delta`/`present_a`/`present_b`/`both_missing`/`equal`）与四阶段状态对照
- `GET  /api/jobs/{id}`
- `GET  /api/jobs/{id}/stages`

> 差分结果只由 `/api/jobs/diff` 在服务端计算；前端不得通过拉取两条 `/api/jobs/{id}` 详情自行相减来冒充差分接口。

## 本地单测（可选）

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

覆盖：畸形 FASTQ 在 `ParseActor` 失败；正常样例产出 `mean_quality`；差分接口的成功/失败对照、单侧缺失、有符号差值、auditor 可读不可提交（403）、未登录 401、相同作业 400 / 不存在 404。

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
    tests/{conftest,test_actors,test_diff_api}.py
  frontend/
    Dockerfile nginx.conf
    src/pages/{Login,Samples,JobSubmit,JobDetail,JobHistory,JobDiff}Page.vue
```
