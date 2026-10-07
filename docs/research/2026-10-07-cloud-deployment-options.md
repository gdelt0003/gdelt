# GDELT 云端部署与定时计算平台调研

**核验日期：** 2026-10-07（UTC+8）

**项目场景：** GDELT 静态新闻观察台；事件、视频、A 股及视觉索引由定时后台生成 JSON，前端静态发布。计算、刷新、构建与部署应全部在云端执行，本机只保存源代码。
**范围：** 基于平台官方文档与价格页面做定性比较，不迁移服务、不估算未实测的月账单。

## 结论摘要

没有对所有维度都胜过 GitHub 的单一平台。该项目仓库现为公开仓库，标准 GitHub-hosted Actions runner 对公开仓库免费；Pages 也可由 Actions 工作流发布。若目标是最低迁移成本，先完善现有 Actions/Pages 的失败门禁、云端 CI 和产物验证，比迁移更直接。

若需要长时间容器作业及独立持久化数据层，首选 **Cloud Run Jobs + Cloud Scheduler + Cloud Storage + Cloud CDN/Firebase Hosting**；若优先降低运维配置量，可考虑 **Render Cron + Static Sites + 外部对象存储**；已有 AWS 运维能力、重视网络和权限控制时，可考虑 **EventBridge Scheduler + ECS Fargate + S3/CloudFront**。

所有金额均为公开美元计价方式或额度摘要，未根据未实测的作业时长、CPU、内存、存储和流量推算项目月费。平台支持“定时调度”并不意味着每次一定准点执行；数据刷新与页面部署应分别观察。

## 候选方案比较

| 排名 | 云端方案 | 调度和工作负载适配 | 费用模型、持久化及主要限制 |
|---|---|---|---|
| 1 | **Google Cloud Run Jobs + Cloud Scheduler + Cloud Storage + Cloud CDN / Firebase Hosting** | 容器化 Python 作业；Cloud Scheduler 使用分钟级 cron。Cloud Run Job 单任务默认上限 10 分钟，可配置到 168 小时。可以把耗时分析与静态站点发布解耦。 | Scheduler 标价约 **$0.10/job/31 天**（免费额度需按账户核实）；Cloud Run 按 vCPU/GiB 时间及区域计费，并有列明的月免费额度；GCS、网络/CDN另计。支持 Cloud Logging、Secret Manager 和耐久对象存储。需搭建镜像、IAM、注册表与发布通路，锁定程度中高。适合长任务，但需承担首次云资源配置。 |
| 2 | **Render Cron Jobs + Static Sites + 外部对象存储** | 可从 Git 或容器运行 Python；静态站支持 Git 自动部署和 CDN。Cron 作业最长 12 小时、单服务最多一个并发；前一次未结束时，后续排程会延后。文档没有明确准点 SLA 或最小间隔保证。 | Cron 服务至少 **$1/月**，另按资源使用计费；Static Sites 可免费部署，但带宽及 pipeline minutes 受 workspace 额度影响。提供运行日志、环境变量和 secret files。**Cron 不支持持久盘**，需使用 S3/R2/Git API 等外部存储保存 JSON。适配容易、维护较低。 |
| 3 | **AWS EventBridge Scheduler + ECS Fargate + S3/CloudFront** | 容器定时运行；Schedule 为分钟级，触发精度可放宽到最多 60 秒，并支持重试/灵活窗口。适合较长 Python 作业。 | Scheduler 按调用量计费；Fargate 按 vCPU、内存、秒计价，S3/CloudFront 另计请求、存储和流量。使用 CloudWatch Logs、Secrets Manager、S3。网络、IAM/VPC、镜像注册表等初始化较复杂，但权限与网络控制强，适合已有 AWS 运维能力的团队。 |
| 4 | **Azure Container Apps Jobs + Azure Static Web Apps + Blob Storage** | 容器型计划任务加静态站点；可设置 cron、重试、并发与超时。适合将 Python 分析放到容器作业。 | Container Apps 按资源秒计费；官方列有每月每订阅 180k vCPU 秒、360k GiB 秒、2M 请求的免费 grant；具体区域价格应临部署时核算。可使用 Azure Monitor、Key Vault、Blob。中高平台绑定，需配置注册表和身份权限。 |
| 5 | **Railway Cron + Railway 服务 / 外部静态 CDN** | Cron 字段精确到分钟，但官方未承诺准点 SLA。当前任务未结束时，下一次运行会被跳过而非排队。没有与 Pages 等同的独立全球静态站产品，可部署公开服务或搭配 Cloudflare Pages/CDN。 | Free 提供 **$1/月使用额度**且内存上限 0.5GB；Hobby **$5/月**含 $5 使用额度，日志 7 天；Pro **$20/月**含 $20 使用额度，日志 30 天。超额按 CPU/内存等计价。支持变量和 volumes；需核对 Cron 与 volume 适配，或使用对象存储。 |
| 6 | **Cloudflare Workers Cron + Workers Static Assets + R2** | 静态资产与边缘 Worker 可一次原子发布，全球 CDN 能力强，Cron 分钟级。**每次 CPU 上限限制重任务**：付费计划小于 1 小时间隔时每次 30 秒 CPU，1 小时及以上最高 15 分钟；内存 128MB。若仍使用 Torch/Transformers 或当前长时任务设置，不适合原样迁移；适合拆分、轻量化后的任务。 | Workers Paid 起价 **$5/月**并包含请求/CPU额度；R2 每月包含 10GB 存储、1M A 类、10M B 类操作，公网 egress 免费。提供日志/指标/环境变量和 R2 持久化。适合作 CDN/对象存储层，不是当前长作业的直接替代。 |
| 7 | **GitLab CI scheduled pipelines + GitLab Pages** | 与 GitHub Actions + Pages 最接近的一体方案；CI runner 可运行 Python 容器，Pages 随 CI/CD 部署。计划频率受实例限制，部署前应检查实例配置。 | Free **$0、400 compute minutes/月、10GiB storage**；Premium 标价 **$29/用户/月**、10k分钟/月。免费分钟可能被高频批处理消耗；artifact 有保留与容量限制。提供 CI variables 和日志。迁仓和 GitHub 集成调整有成本。 |
| 8 | **Netlify Scheduled/Background Functions + CDN + Blobs** | 静态站点、CDN 和预览部署体验好；Scheduled Function 运行上限 30 秒，Background Function 最长 15 分钟，低于长时间容器作业。可用于轻作业或仅触发外部容器。 | Free **300 credits**；Personal **$9/月/1000 credits**；Pro **$20/月/3000 credits**。计算、部署与流量按 credits 消耗。提供日志、环境变量及 Blobs。若外接容器，运维会变成组合方案。 |
| 9 | **Vercel Cron + 静态部署/CDN** | Hobby Cron 最多每日一次且时间精度可到 ±59 分钟；Pro/Enterprise 支持分钟级。Function 运行上限 Hobby 300 秒、Pro 800 秒，扩展 Beta 最高 1800 秒；不适合直接承载当前最长作业设置。 | Hobby **$0**，Pro **$20/月**，Function/带宽按套餐额度与超额价计。平台日志、环境变量；持久数据需接 Blob 或外部对象存储。部署预览/CDN强，长作业需另找容器执行层。 |
| 10 | **Supabase Cron + Postgres/Edge Functions + Cloudflare Pages** | Cron 可高频触发，支持 job run 记录；官方建议单 job 不超过 10 分钟、并发不超过 8。Edge Function 256MB，单请求 CPU 时间 2 秒，墙钟时间 Free 150 秒/付费 400 秒；不适合当前重批处理，且静态站需另配 Pages。 | Free；Pro **$25/月起**。可用 Postgres、日志、Edge secrets 做结构化状态和轻 API。适合轻量触发器/状态层，不是 Python/ML 长任务替身，平台绑定较高。 |

## GitHub 基线与工作流注意事项

- **Actions 公开仓库 runner 通常免费**；若转为私有，额度因账户方案而异。公开仓库的 Actions/Pages 已是很强的低成本起点，替换理由更可能是调度保证、长容器任务和对象存储边界，而不是单纯省费。
- GitHub schedule 最小间隔为 5 分钟，但繁忙时可能延迟甚至丢弃；workflow 必须位于默认分支。公开仓库长期无活动时，计划任务可能被自动停用。应监控最近成功时间，而非只看 schedule 声明。
- `GITHUB_TOKEN` 写回仓库产生的 push 不会自动启动另一个常规 `push` workflow；需要显式 `workflow_dispatch`/`repository_dispatch` 或重新设计为单个 workflow 内的 job 依赖。
- 页面部署、数据分析与视频分析的运行时间、p95、失败率、数据增长、网络量未在本报告核算；workflow `timeout-minutes` 是最大时限，不是实际运行时长。

## 对本项目的建议路线

1. **近期继续用 Actions + Pages，先补稳健性：** 让采集失败直接失败；生成后校验 JSON 和更新时间，失败不得覆盖 `latest`；部署前加入云端 CI；限制 Pages 上传内容并监控 artifact 大小。
2. **先量测，再迁长作业：** 在 Actions 中记录每个分析任务的运行时间和输出大小。只有确认长时运行/额度成为瓶颈后，才将重任务容器化迁至 Cloud Run Jobs、ECS Fargate 或 Azure Container Apps Jobs。
3. **数据与前端解耦：** 把 `latest.json` 和历史快照迁到具备版本/生命周期策略的对象存储（GCS、S3 或 R2），前端读取稳定 URL；避免每次数据更新增长 Git 历史并重建整个静态站。
4. **优先候选：** 需要长作业且少管理基础设施时先做 GCP Cloud Run PoC；优先少配置时评估 Render；已有 AWS 能力时评估 Fargate。可单独以 Cloudflare 提供静态/CDN及对象分发，但不可假设 Workers 能承载 Torch 等长任务。

## 官方来源（核验日期：2026-10-07）

- GitHub： [Actions 计费](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[Pages 限制](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)、[Hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)、[schedule 触发规则](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- Google Cloud： [Cloud Run Jobs](https://docs.cloud.google.com/run/docs/create-jobs)、[任务时限](https://docs.cloud.google.com/run/docs/configuring/task-timeout)、[Scheduler 定价](https://cloud.google.com/scheduler/pricing)、[Cloud Run 定价](https://cloud.google.com/run/pricing)、[Firebase Hosting 额度](https://firebase.google.com/docs/hosting/usage-quotas-pricing)
- Render： [Cron Jobs](https://render.com/docs/cronjobs)、[Static Sites](https://render.com/docs/static-sites)、[定价](https://render.com/pricing)、[环境变量/Secrets](https://render.com/docs/configure-environment-variables)
- AWS： [Scheduler 类型](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html)、[ECS 定时任务](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/tasks-scheduled-eventbridge-scheduler.html)、[Scheduler 配额](https://docs.aws.amazon.com/scheduler/latest/UserGuide/scheduler-quotas.html)、[EventBridge 定价](https://aws.amazon.com/eventbridge/pricing/)
- Azure： [Container Apps Jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs)、[Container Apps 定价](https://azure.microsoft.com/en-us/pricing/details/container-apps/)、[Static Web Apps 定价](https://azure.microsoft.com/en-us/pricing/details/app-service/static/)
- Railway： [Cron Jobs](https://docs.railway.com/cron-jobs)、[定价](https://railway.com/pricing)、[Volumes](https://docs.railway.com/volumes/reference)
- Cloudflare： [Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)、[Workers 限制](https://developers.cloudflare.com/workers/platform/limits/)、[Workers 定价](https://developers.cloudflare.com/workers/platform/pricing/)、[Static Assets](https://developers.cloudflare.com/workers/static-assets/)、[R2 定价](https://developers.cloudflare.com/r2/pricing/)
- GitLab： [Scheduled pipelines](https://docs.gitlab.com/ci/pipelines/schedules/)、[Pages](https://docs.gitlab.com/user/project/pages/)、[定价](https://about.gitlab.com/pricing/)
- Netlify： [Scheduled functions](https://docs.netlify.com/build/functions/scheduled-functions/)、[Background functions](https://docs.netlify.com/build/functions/background-functions/)、[定价与 credits](https://www.netlify.com/pricing/)
- Vercel： [Cron 用量与定价](https://vercel.com/docs/cron-jobs/usage-and-pricing)、[函数限制](https://vercel.com/docs/functions/limitations)、[定价](https://vercel.com/pricing)
- Supabase： [Cron](https://supabase.com/docs/guides/cron)、[Edge Function 限制](https://supabase.com/docs/guides/functions/limits)、[定价](https://supabase.com/pricing)
