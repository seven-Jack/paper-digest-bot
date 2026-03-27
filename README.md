# 📚 Paper Digest Bot

**Automated daily academic paper digest with AI analysis and adaptive keyword weighting.**

[中文文档](README_CN.md) | [Setup Wizard](setup/index.html)

## Features

- **Multi-source fetching** — arXiv, APS (PRL/PRA/PRX), Nature, Science
- **AI-powered analysis** — Gemini / OpenAI / Claude summarize each paper in your language
- **Adaptive keyword weights** — Vote on papers to teach the system your interests
- **DOI bootstrapping** — Provide reference papers to auto-extract initial keywords
- **Email digest** — Beautiful HTML email with inline vote buttons
- **100% free** — Runs entirely on GitHub Actions + free AI tier
- **Open source template** — Click "Use this template" and configure in minutes

## How It Works

```
Reference DOIs → Extract Keywords → Daily Fetch → Filter by Weights
                                                        ↓
                                              AI Analysis (Gemini/GPT/Claude)
                                                        ↓
                                              HTML Email with Vote Links
                                                        ↓
                                              You Vote → Update Weights → Loop
```

Papers you mark as "very relevant" boost related keyword weights. Papers marked "not interested" gradually reduce those keywords. Keywords that decay below a threshold are automatically deactivated.

## Quick Start (4 Steps)

1. **Create your repo** — Click **"Use this template"** → generate your own repository

2. **Set Secrets** — Settings → Secrets and variables → Actions, add:
   | Secret | Description |
   |--------|-------------|
   | `GEMINI_API_KEY` | Google AI API key ([get free key](https://aistudio.google.com/apikey)) |
   | `EMAIL_ADDRESS` | Your Gmail address |
   | `EMAIL_PASSWORD` | Gmail App Password ([create one](https://myaccount.google.com/apppasswords)) |

3. **One-click config** — Actions tab → **"⚙️ Setup: Generate Configuration"** → fill the form → Run workflow
   (Auto-generates and commits `config.yaml` — no manual file editing needed!)

4. **Bootstrap keywords** — Actions tab → **"Bootstrap Keywords from DOIs"** → enter your reference DOIs → Run workflow

Done! The system will send a daily paper digest to your email at your configured time.

> **Voting**: The first time you click a vote button in the email, you'll need to enter a GitHub Personal Access Token ([create one](https://github.com/settings/tokens/new?scopes=repo&description=PaperDigestVote)). Your browser remembers it for one-click voting afterwards.

### Optional: Enable GitHub Pages (Recommended)

Enable GitHub Pages for the best one-click voting experience:

Settings → Pages → Source: `main` / `/(root)` → Save

## Configuration

### config.yaml

```yaml
ai_provider: gemini          # gemini / openai / claude

email:
  language: zh               # zh = Chinese, en = English
  max_papers: 20

sources:
  arxiv:
    enabled: true
    categories:
      - physics.atom-ph
      - quant-ph
  aps:
    enabled: true
    journals:
      - prl
      - pra

weights:
  daily_decay: 0.02          # Weight lost per day without votes
  min_threshold: 0.1         # Keywords below this are deactivated
```

### AI Providers

| Provider | Secret Name | Free Tier | Get Key |
|----------|------------|-----------|---------|
| Gemini | `GEMINI_API_KEY` | 15 req/min | [AI Studio](https://aistudio.google.com/apikey) |
| OpenAI | `OPENAI_API_KEY` | Paid only | [Platform](https://platform.openai.com/api-keys) |
| Claude | `ANTHROPIC_API_KEY` | Paid only | [Console](https://console.anthropic.com/) |

## Voting System

Each paper in the digest email has three vote buttons:

- 👎 **Not interested** — Reduces weight of matched keywords (-0.2)
- 👌 **Neutral** — No weight change
- 🔥 **Very relevant** — Boosts weight of matched keywords (+0.3)

Votes are processed via GitHub Actions `workflow_dispatch`. Over time, the system learns your preferences and delivers increasingly relevant papers.

## Adding New Journal Sources

Create a new fetcher in `src/fetchers/` following this pattern:

```python
class MyJournalFetcher:
    def __init__(self, config):
        pass

    def fetch(self, days_back=2) -> list[dict]:
        # Return list of paper dicts with:
        # id, title, abstract, authors, url, published, source, doi
        return [...]
```

Then register it in `main.py`. PRs welcome!

## Project Structure

```
paper-digest-bot/
├── .github/workflows/
│   ├── daily_digest.yml      # Cron job: fetch → analyze → email
│   ├── vote_handler.yml      # Process vote from email links
│   └── bootstrap.yml         # Initialize keywords from DOIs
├── src/
│   ├── fetchers/
│   │   ├── arxiv_fetcher.py
│   │   └── aps_fetcher.py
│   ├── analyzer.py           # Multi-provider AI analysis
│   ├── weight_manager.py     # Adaptive keyword weights
│   ├── email_builder.py      # HTML email generation
│   ├── email_sender.py       # SMTP sending
│   └── config_loader.py
├── data/
│   ├── keywords.json         # Your keyword weights (auto-managed)
│   └── paper_cache.json      # Deduplication cache
├── setup/
│   └── index.html            # Setup wizard (GitHub Pages)
├── bootstrap.py              # DOI keyword extraction
├── main.py                   # Entry point
├── config.example.yaml
└── requirements.txt
```

## License

MIT License. See [LICENSE](LICENSE).
