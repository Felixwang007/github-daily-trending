# 🔥 GitHub Trending Daily

> 每天自动追踪 GitHub 最热门的开源项目 · 零API依赖 · 全自动化

[![Daily Trending Deploy](https://github.com/Felixwang007/github-daily-trending/actions/workflows/deploy.yml/badge.svg)](https://github.com/Felixwang007/github-daily-trending/actions/workflows/deploy.yml)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-brightgreen)](https://Felixwang007.github.io/github-daily-trending)
[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-%E2%9D%A4%EF%B8%8F-bf4b8a)](https://github.com/sponsors/Felixwang007)

## 📋 概述

这是一个**全自动化的GitHub Trending聚合站**，无需任何第三方API Key，完全依靠 GitHub Actions + GitHub Pages 驱动：

- ⚡ **自动采集** — 每6小时自动抓取 GitHub Trending
- 🚀 **零成本部署** — GitHub Pages 免费托管
- 🔧 **零API依赖** — 直接解析HTML，不需要 GitHub Token
- 📱 **响应式设计** — 移动端友好
- 🤖 **全自动运维** — 只要GitHub不宕机，它就永远在线

## 🚀 快速上手（1分钟）

```bash
# 1. Clone
git clone https://github.com/Felixwang007/github-daily-trending.git
cd github-daily-trending

# 2. 本地测试
python scripts/fetch_trending.py

# 3. 推送到 GitHub（自动触发部署）
git push origin main
```

## 💰 赚钱逻辑

这个项目通过以下方式产生价值：

### 1. GitHub Sponsors（被动收入）
Repo 已经配置了 `FUNDING.yml`，访客看到项目有价值就会赞助。

### 2. Buy Me a Coffee / Ko-fi
页面顶部有捐助按钮，每天有数百开发者浏览该站。

### 3. Google AdSense（后期可加）
如果流量上去了（预计每月几万PV），可以加Google AdSense广告。

### 4. 影响力变现
- 自动生成的技术内容提升你的开发者影响力
- 可扩展到多个细分领域（AI、前端、Rust等）
- 建立 "GitHub自动化专家" 的品牌

## 🏗️ 进阶玩法

这个模板可以扩展到：

| 方向 | 描述 | 技术栈 |
|------|------|--------|
| 📰 **AI工具日报** | 采集AI相关新闻/RSS | Python + GitHub Actions |
| 📊 **开发者周刊** | 汇总技术文章 | Markdown + Actions |
| 🛠️ **DevOps工具链** | 自动化运维聚合 | Shell + Actions |
| 📈 **加密货币/股票** | 价格趋势监控 | Python + Actions |
| 🎯 **Hacker News热帖** | Hacker News聚合 | Python + Actions |
| 📝 **CSDN/掘金自动发文** | Playwright自动化发布 | Playwright + Actions |

## 📂 项目结构

```
github-daily-trending/
├── .github/workflows/
│   └── deploy.yml        # GitHub Actions 自动部署
├── scripts/
│   └── fetch_trending.py # 数据采集 + 站点生成
├── site/                 # 生成的静态文件
│   ├── index.html
│   └── trending.json     # 结构化数据
├── .gitignore
├── FUNDING.yml          # GitHub Sponsors 配置
└── README.md
```

## 🔄 自动化管线

```
GitHub Trending HTML
        ↓ (Python scraping, no API key)
   JSON结构化数据
        ↓ (Python template generation)
  静态HTML网站
        ↓ (GitHub Actions deploy)
  GitHub Pages (felixwang007.github.io/github-daily-trending)
        ↓ (每6小时自动循环)
  自动更新
```

## ⭐ Star History

如果你觉得这个项目有用，请点个⭐支持！

## 📄 License

MIT
