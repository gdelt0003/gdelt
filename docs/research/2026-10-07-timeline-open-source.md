# 时间线与新闻聚合开源项目调研

**核验日期：** 2026-10-07

**项目背景：** 当前 `gdelt0003/gdelt` 是无前端构建步骤的静态 GDELT 新闻观察台；数据由云端 GitHub Actions 生成。本报告比较可借鉴的新闻聚合与时间线项目，不将独立服务框架误作可直接嵌入的 UI 组件。

## 结论

- **时间轴 UI：** `visjs/vis-timeline` 是当前静态 HTML 最匹配的候选。MIT 或 Apache-2.0 双许可，提供 standalone UMD，可固定版本引入，无需 React/build pipeline。
- **地图 UI：** Leaflet 是低依赖地图首选（BSD-2-Clause）。但只有输入含有效经纬度时才绘点；GDELT 地名坐标属于粗略地理标注，不是活动现场或人员位置。地图瓦片服务需要单独核对使用政策并展示署名。
- **新闻聚合领域模型：** `KKKKhazix/AIHOT` 是最匹配的 AIHOT 项目，不是时间线组件。可参考 RSS/API/X 采集、事件聚类、多来源权重及编辑精选；不建议把它的 Node/React/PostgreSQL 服务栈整体搬进当前静态站。
- **总统活动产品边界：** 当前站点不是总统行踪站。任何未来活动档案须先完成单独的来源清单和采集设计，只展示公开、延迟至少 24 小时的历史材料；不展示实时位置、路线或未来行程。用户明确提及的 X/Twitter 普通推文、YouTube 和 FAA NOTAM 均应列入待评估来源；NOTAM 只作为航空通告线索，不能单独证明总统行程或位置。百源调研清单仍须单独完成，不代表本报告已核验 100 个源。

## 候选对照

Star 数与默认分支最近提交日期是 2026-10-07 调研时的 GitHub API 快照，不是性能指标；许可证依据对应仓库许可文本，采用前应复核仓库、完整依赖和分发方式。

| 项目 | Stars / 最近提交 | 许可证 | 能力、适配与限制 |
|---|---:|---|---|
| [KKKKhazix/AIHOT](https://github.com/KKKKhazix/AIHOT) | 6,276 / 2026-10-07 | MIT；名称和 Logo 不在许可范围内 | 可配置 RSS、网页列表、JSON、X 等源，做模型评分、事件聚类、多源热度排序、日报周报并输出 RSS/API/MCP。数据/编辑流程可借鉴；Node 24、React Router SSR、Fastify、PostgreSQL、pg-boss、Docker 与模型 API 不适合直接合并到无构建的静态站。 |
| [NUKnightLab/TimelineJS3](https://github.com/NUKnightLab/TimelineJS3) | 3,224 / 2026-09-22 | MPL-2.0 | 多媒体叙事与时间导航，适合少量编辑精选专题；不是密集新闻筛选 feed。修改其 MPL 覆盖文件时须遵守源码提供义务。 |
| [prabhuignoto/react-chrono](https://github.com/prabhuignoto/react-chrono) | 4,203 / 2025-12-29 | MIT | 新闻 feed、媒体卡、搜索、键盘与国际化。可作视觉参考或 React 迁移候选；当前站点无 React 构建，近期活跃度相较其他候选偏低。 |
| [visjs/vis-timeline](https://github.com/visjs/vis-timeline) | 2,565 / 2026-08-22（近期 push 2026-10-05） | MIT OR Apache-2.0 | 原生 JS、standalone UMD；支持时间点、区间、分组与缩放。当前最适合固定发行版本后集成；限制视窗内项目数量，统一 UTC 日期与重复事件。 |
| [namespace-ee/react-calendar-timeline](https://github.com/namespace-ee/react-calendar-timeline) | 2,160 / 2026-07-24 | MIT | 分组、拖动/缩放、排程型时间轴，适合“计划/实际”对照；依赖 React、React DOM、Day.js，非当前轻静态栈首选。 |
| [keplergl/kepler.gl](https://github.com/keplergl/kepler.gl) | 12,035 / 2026-10-06 | MIT | 大规模空间数据与时间过滤工作台；React/Redux、MapLibre、deck.gl 依赖较重，且底图/令牌方案需验证。 |
| [visgl/deck.gl](https://github.com/visgl/deck.gl) | 14,631 / 2026-10-06 | MIT | WebGL 大数据图层、轨迹与聚合；适合海量时空数据，不适合现阶段的小型静态新闻快照。 |
| [maplibre/maplibre-gl-js](https://github.com/maplibre/maplibre-gl-js) | 11,813 / 2026-10-07 | BSD-3-Clause | 矢量 WebGL 底图；需独立选瓦片/样式服务并遵守归属、服务条款。可作为后续复杂地图备选。 |
| [Leaflet/Leaflet](https://github.com/Leaflet/Leaflet) | 45,710 / 2026-09-19 | BSD-2-Clause | 轻量普通 JS 地图，适合少量地名点与 GeoJSON；可与 vis-timeline 组合。瓦片服务条款、限流和 attribution 另行负责。 |
| [d3/d3](https://github.com/d3/d3) | 113,812 / 2026-05-28 | ISC | 自定义 SVG/Canvas/HTML 可视化自由度高，但时间轴细节与交互都需自行维护。 |
| [apache/echarts](https://github.com/apache/echarts) | 67,459 / 2026-10-04 | Apache-2.0 | 时间轴缩放、事件密度和来源分布图较合适；不替代故事卡片，需保留依赖许可/NOTICE。 |
| [frappe/gantt](https://github.com/frappe/gantt) | 6,138 / 2026-03-05 | MIT | 轻量甘特图适合时间区间；任务依赖/可编辑计划交互容易误导，不是新闻 feed 首选。 |

## 已选择的集成策略

1. 保持静态 HTML 与云端 Actions 产出 JSON；不引入 React 构建系统或常驻服务。
2. 在首页接入版本固定的 vis-timeline 时间轴，以现有 GDELT 日级事件计数为输入；保留既有滑块和条形图作为键盘/降级路径。
3. 当前 GKG 位置解析仅输出地点名和国家、没有坐标，因此 Leaflet 不应通过地名猜点；只有后端解析到有效 GDELT 经纬度并在云端验证后，才呈现“近似地点”地图，并清楚说明坐标不是人员定位。
4. AIHOT 仅作领域模型参考：以后需要聚合多类官方及公开媒体源时，可借鉴来源元数据、事件去重/聚类、来源权重和更正链；不要直接复制其品牌或整体服务栈。

## 许可与外部依赖

- 时间轴和地图发行文件使用固定版本 CDN 时，浏览器需访问相应 CDN；不得使用 `latest` 浮动标签。若改为仓库内再分发，应同时纳入完整许可文本/NOTICE。
- vis-timeline：MIT OR Apache-2.0，发行项目：[npm](https://www.npmjs.com/package/vis-timeline)，许可文本：[MIT](https://github.com/visjs/vis-timeline/blob/master/LICENSE.MIT.txt) / [Apache-2.0](https://github.com/visjs/vis-timeline/blob/master/LICENSE.Apache-2.0.txt)。
- Leaflet：BSD-2-Clause，发行项目：[npm](https://www.npmjs.com/package/leaflet)，许可文本：[LICENSE](https://github.com/Leaflet/Leaflet/blob/main/LICENSE)。
- TimelineJS3、MapLibre 等其他候选的完整许可、传递依赖与署名义务须在实际采用时重新核验。当前仓库未见根目录项目许可证；本报告不替项目授予新许可。

## 核验链接

候选仓库主页与许可证已链接在表格内。其他主要核验页面： [AIHOT README](https://github.com/KKKKhazix/AIHOT#这是什么)、[TimelineJS3 README](https://github.com/NUKnightLab/TimelineJS3#overview)、[React Chrono README](https://github.com/prabhuignoto/react-chrono#timeline-modes)、[vis-timeline README](https://github.com/visjs/vis-timeline#install)、[React Calendar Timeline README](https://github.com/namespace-ee/react-calendar-timeline#readme)、[Kepler README](https://github.com/keplergl/kepler.gl#readme)、[deck.gl README](https://github.com/visgl/deck.gl#readme)、[MapLibre README](https://github.com/maplibre/maplibre-gl-js#readme)、[Leaflet README](https://github.com/Leaflet/Leaflet#readme)、[D3 README](https://github.com/d3/d3#readme)、[ECharts README](https://github.com/apache/echarts#readme)、[Frappe Gantt README](https://github.com/frappe/gantt#readme)。
