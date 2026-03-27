# Paper Digest Bot - 修改说明

## 版本：Bootstrap Mode Update

本次修改主要实现两个目标：
1. **早期宽泛检索模式** - 初期推送所有相关论文，通过投票逐渐精准
2. **扩大文献检索范围** - 新增数据源和扩展 arXiv 分类

---

## 📁 修改的文件

### 1. `config.yaml` - 配置文件

**新增配置项：**

```yaml
# Bootstrap 模式配置
bootstrap:
  enabled: true                    # 启用宽泛检索模式
  min_score_threshold: 0.0         # 初期阈值设为0
  auto_disable_after_votes: 100    # 100次投票后自动切换到正常模式

# 抓取配置
fetch:
  days_back: 2
  max_results_per_source: 50
```

**扩展的数据源：**
- arXiv：新增 `physics.optics`, `cond-mat.quant-gas`, `cond-mat.mes-hall` 等分类
- APS：新增 `prxquantum`
- Semantic Scholar：新增（通过关键词搜索）
- OpenAlex：新增（通过 concept ID 搜索）

---

### 2. `main.py` - 主程序

**新增功能：**
- `is_bootstrap_mode()` - 检测是否处于 bootstrap 模式
- 修改 `filter_and_rank()` - 支持宽松过滤
- Bootstrap 模式下，未匹配关键词的论文也会被包含（给予基础分数）

**工作流程：**
```
检查 Bootstrap 模式
       ↓
    启用？ ─── 否 ──→ 使用正常阈值过滤
       │
      是
       ↓
使用宽松阈值 (0.0)
       ↓
未评分论文也保留
       ↓
累计投票 >= 100？
       │
      是
       ↓
自动切换到正常模式
```

---

### 3. `src/weight_manager.py` - 权重管理器

**新增功能：**
- 投票统计：记录 `total_votes` 用于自动模式切换
- `votes_by_type` 统计各类投票数量
- `deactivated_keywords` 记录被停用的关键词
- 增强的 `process_vote()` 方法

**数据结构：**
```json
{
  "keywords": {
    "quantum": {
      "weight": 1.5,
      "source": "bootstrap",
      "vote_count": 3,
      "last_voted": "2026-03-27T..."
    }
  },
  "stats": {
    "total_votes": 42,
    "votes_by_type": {
      "not_interested": 10,
      "neutral": 20,
      "very_relevant": 12
    }
  },
  "deactivated_keywords": [...]
}
```

---

### 4. 新增文件

#### `src/fetchers/semantic_scholar_fetcher.py`
- Semantic Scholar API 抓取器
- 支持按学科领域和关键词搜索
- 免费 API，无需 API Key

#### `src/fetchers/openalex_fetcher.py`
- OpenAlex API 抓取器
- 支持按 concept ID 和关键词搜索
- 完全免费开放的学术图谱
- 支持重建 inverted index 格式的摘要

---

## 🚀 使用方法

### 1. 替换文件
将修改后的文件替换到你的仓库中：
- `config.yaml`
- `main.py`
- `src/weight_manager.py`
- `src/fetchers/semantic_scholar_fetcher.py`（新文件）
- `src/fetchers/openalex_fetcher.py`（新文件）

### 2. 启动 Bootstrap 模式
默认已启用，配置中 `bootstrap.enabled: true`

### 3. 开始投票训练
- 每天收到论文后，对感兴趣的论文点击 🔥
- 对不感兴趣的论文点击 👎
- 系统会自动学习你的偏好

### 4. 自动切换
累计 100 次投票后，系统自动切换到正常模式，开始精准过滤

### 5. 手动切换（可选）
如果想提前退出 Bootstrap 模式，在 `config.yaml` 中设置：
```yaml
bootstrap:
  enabled: false
```

---

## 📊 数据源详情

| 数据源 | 类型 | 免费 | 说明 |
|--------|------|------|------|
| arXiv | 预印本 | ✅ | 物理/数学/CS 核心来源 |
| APS | 期刊 | ✅ | Physical Review 系列 |
| Nature | 期刊 | ✅ | 顶级综合期刊 |
| Science | 期刊 | ✅ | 顶级综合期刊 |
| Semantic Scholar | 聚合 | ✅ | AI 驱动的学术搜索 |
| OpenAlex | 图谱 | ✅ | 2.5亿+ 论文的开放图谱 |

---

## ⚙️ 配置调整建议

根据你的需求，可以调整以下参数：

```yaml
# 如果每天论文太多
email:
  max_papers: 30  # 减少数量

# 如果想更快进入精准模式
bootstrap:
  auto_disable_after_votes: 50  # 减少投票阈值

# 如果想让权重变化更明显
weights:
  vote_values:
    not_interested: -0.5  # 增大负向惩罚
    very_relevant: 0.8    # 增大正向奖励
```

---

## 🔧 故障排除

### Q: Semantic Scholar 或 OpenAlex 抓取失败？
A: 这两个数据源是可选的，失败不影响其他源。查看日志中的警告信息。

### Q: 论文数量太少？
A: 检查 `bootstrap.min_score_threshold` 是否设为 0，确保 Bootstrap 模式正常启用。

### Q: 如何查看当前投票统计？
A: 查看 `data/keywords.json` 文件中的 `stats` 字段。

---

## 📝 后续优化建议

1. **添加更多数据源**：如 PubMed、bioRxiv（如果扩展到生物领域）
2. **智能关键词提取**：从高分论文中自动提取新关键词
3. **周报/月报**：汇总投票统计和趋势分析
