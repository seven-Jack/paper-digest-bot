# 📚 Paper Digest Bot — 学术论文智能日报

**每日自动检索学术论文，AI 分析摘要，邮件推送，支持投票反馈自适应推荐。**

[English](README.md) | [配置向导](setup/index.html)

## 功能特点

- **多源检索** — arXiv、APS (PRL/PRA/PRX)、Nature、Science
- **AI 智能分析** — Gemini / OpenAI / Claude 对每篇论文进行中文摘要分析
- **自适应权重** — 通过邮件投票打分，系统自动学习你的兴趣偏好
- **DOI 冷启动** — 提供几篇参考文献 DOI，自动提取研究关键词
- **精美邮件** — HTML 格式邮件，内嵌一键投票按钮
- **完全免费** — GitHub Actions + 免费 AI API，零成本运行
- **开源模板** — 点击 "Use this template" 几分钟即可完成配置

## 工作原理

```
参考文献 DOI → 提取关键词 → 每日检索新论文 → 关键词权重过滤
                                                    ↓
                                          AI 分析（Gemini/GPT/Claude）
                                                    ↓
                                          生成 HTML 邮件 + 投票链接
                                                    ↓
                                          用户投票 → 更新权重 → 循环
```

你标记为「非常相关」的论文会提升相关关键词权重，「不感兴趣」会逐渐降低权重。当某个关键词权重降至阈值以下时，系统自动停止检索该方向。

## 快速开始（4 步完成）

1. **创建仓库** — 点击 **"Use this template"** → 生成你自己的仓库

2. **设置 Secrets** — Settings → Secrets and variables → Actions，添加：
   | Secret 名称 | 说明 |
   |-------------|------|
   | `GEMINI_API_KEY` | Google AI API 密钥（[免费获取](https://aistudio.google.com/apikey)） |
   | `EMAIL_ADDRESS` | 你的 Gmail 地址 |
   | `EMAIL_PASSWORD` | Gmail 应用专用密码（[创建方法](https://myaccount.google.com/apppasswords)） |

3. **一键配置** — Actions 标签 → **"⚙️ Setup: Generate Configuration"** → 填表 → Run workflow
   （自动生成 config.yaml 并提交，无需手动创建文件！）

4. **初始化关键词** — Actions 标签 → **"Bootstrap Keywords from DOIs"** → 输入你的参考文献 DOI → Run workflow

完成！系统会在每天早上 8:00（北京时间）自动发送论文日报到你的邮箱。

> **投票说明**：首次点击邮件中的投票按钮时，需要输入一次 GitHub Personal Access Token（[创建方法](https://github.com/settings/tokens/new?scopes=repo&description=PaperDigestVote)），之后浏览器会记住，实现真正的一键投票。

### 可选：启用 GitHub Pages（推荐）

启用 GitHub Pages 可以让投票按钮实现一键投票体验：

Settings → Pages → Source 选 `main` / `/(root)` → Save

## 配置说明

### config.yaml

```yaml
ai_provider: gemini          # 可选: gemini / openai / claude

email:
  language: zh               # zh = 中文, en = 英文
  max_papers: 20             # 每封邮件最多论文数

sources:
  arxiv:
    enabled: true
    categories:              # arXiv 分类
      - physics.atom-ph      # 原子物理
      - quant-ph             # 量子物理
      - physics.comp-ph      # 计算物理
  aps:
    enabled: true
    journals:
      - prl                  # Physical Review Letters
      - pra                  # Physical Review A

weights:
  daily_decay: 0.02          # 每日权重衰减量
  min_threshold: 0.1         # 低于此阈值的关键词停止检索
```

### AI 服务对比

| 服务 | Secret 名称 | 免费额度 | 获取密钥 |
|------|------------|---------|---------|
| Gemini（推荐） | `GEMINI_API_KEY` | 15次/分钟 | [AI Studio](https://aistudio.google.com/apikey) |
| OpenAI | `OPENAI_API_KEY` | 仅付费 | [Platform](https://platform.openai.com/api-keys) |
| Claude | `ANTHROPIC_API_KEY` | 仅付费 | [Console](https://console.anthropic.com/) |

## 投票系统

每封邮件中的每篇论文都有三个投票按钮：

- 👎 **不感兴趣** — 降低匹配关键词的权重（-0.2）
- 👌 **一般** — 权重不变
- 🔥 **非常相关** — 提升匹配关键词的权重（+0.3）

系统会随时间自动学习你的偏好，推送内容会越来越精准。

## 添加新期刊源

在 `src/fetchers/` 中创建新的抓取器，参考以下模式：

```python
class MyJournalFetcher:
    def __init__(self, config):
        pass

    def fetch(self, days_back=2) -> list[dict]:
        # 返回论文字典列表，需包含:
        # id, title, abstract, authors, url, published, source, doi
        return [...]
```

然后在 `main.py` 中注册。欢迎提交 PR！

## 项目结构

```
paper-digest-bot/
├── .github/workflows/
│   ├── daily_digest.yml      # 定时任务：检索 → 分析 → 发邮件
│   ├── vote_handler.yml      # 处理邮件投票
│   └── bootstrap.yml         # DOI 初始化关键词
├── src/
│   ├── fetchers/             # 期刊抓取器（可扩展）
│   ├── analyzer.py           # 多 AI 提供商分析
│   ├── weight_manager.py     # 自适应关键词权重
│   ├── email_builder.py      # HTML 邮件生成
│   └── email_sender.py       # SMTP 发送
├── data/
│   ├── keywords.json         # 关键词权重（自动管理）
│   └── paper_cache.json      # 去重缓存
├── setup/
│   └── index.html            # 配置向导页面
├── bootstrap.py              # DOI 关键词提取
├── main.py                   # 主入口
└── config.example.yaml       # 配置模板
```

## 许可证

MIT License
