# ============================================================
# Passive Recon — GitHub 一键自动化脚本
#
# 功能：
#   1. 创建 v0.1.0 Release
#   2. 创建 M3/M4 里程碑
#   3. 检查 awesome-osint PR #1052 状态
#   4. 创建 GitHub Discussions 公告
#
# 用法（PowerShell，需 GITHUB_TOKEN 环境变量）：
#   $env:GITHUB_TOKEN = "ghp_xxx"   # 或已配置
#   powershell -ExecutionPolicy Bypass -File scripts/github_automation.ps1
#
# 说明：token 从环境变量读取，脚本内不写死任何凭据。
# ============================================================

$ErrorActionPreference = "Stop"

$REPO = "TrueFurina/passive-recon"
$API = "https://api.github.com"
$TOKEN = [System.Environment]::GetEnvironmentVariable("GITHUB_TOKEN", "User")
if (-not $TOKEN) {
    $TOKEN = $env:GITHUB_TOKEN
}
if (-not $TOKEN) {
    Write-Host "❌ 未找到 GITHUB_TOKEN 环境变量，请先配置：" -ForegroundColor Red
    Write-Host '   [System.Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "ghp_xxx", "User")'
    exit 1
}

$HEADERS = @{
    Authorization = "Bearer $TOKEN"
    Accept        = "application/vnd.github.v3+json"
    "User-Agent"  = "passive-recon-automation"
}

function Invoke-GitHub {
    param(
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )
    $uri = "$API$Path"
    $params = @{ Uri = $uri; Method = $Method; Headers = $HEADERS }
    if ($Body) {
        # 关键修复：Body 显式转为 UTF-8 字节，否则 PowerShell 5.1 用 ASCII
        # 编码发送 JSON，中文（如里程碑标题）会变成 ????
        $json = $Body | ConvertTo-Json -Depth 10
        $params.Body = [System.Text.Encoding]::UTF8.GetBytes($json)
        $params.ContentType = "application/json; charset=utf-8"
    }
    try {
        $resp = Invoke-RestMethod @params
        return $resp
    } catch {
        $status = $_.Exception.Response.StatusCode.value__
        $detail = ""
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $detail = $reader.ReadToEnd()
        } catch {}
        Write-Host "⚠️  API $Method $Path → $status $detail" -ForegroundColor Yellow
        return $null
    }
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Passive Recon — GitHub 一键自动化" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# 1. 创建 v0.1.0 Release
# ------------------------------------------------------------
Write-Host "[1/4] 创建 v0.1.0 Release ..." -ForegroundColor Green
$releaseBody = @'
## 🎉 Passive Recon v0.1.0

Purely passive OSINT/EASM/CTEM platform — 20 data sources, zero-touch asset discovery.

### ✨ Features

- **20 passive data sources**: crt.sh, HackerTarget, OTX, URLScan, Wayback Machine, DNSDumpster, CommonCrawl, GitHub, NVD, OSV, Hunter, FOFA, SecurityTrails, Shodan, VirusTotal, ZoomEye, Qichacha, Censys, BinaryEdge
- **🤖 AI**: domain inference, risk scoring, asset classification, natural language chat query
- **Multi-key rotation**: auto-failover when rate-limited (patent-pending method)
- **Health monitoring**: auto-degrade unhealthy sources with cooldown
- **Query cache**: 24h TTL to reduce API cost
- **RBAC**: admin/user token roles for enterprise deployments
- **Compliance report**: periodic audit with violation analysis
- **Web dashboard**: FastAPI panel with asset browsing, risk & CVE views
- **Scheduled tasks**: daily auto-collection with Webhook alerts
- **Asset change alerts**: detect new high-risk assets automatically
- **Docker deployment**: one-command `docker compose up -d`

### 🚀 Quick Start

````bash
pip install -r requirements.txt
python cli.py collect "Tsinghua University"
````

### 📦 Install

````bash
git clone https://github.com/TrueFurina/passive-recon.git
cd passive-recon
pip install -r requirements.txt
````

### 🤝 Contributing

PRs welcome! See [CONTRIBUTING.md](https://github.com/TrueFurina/passive-recon/blob/main/CONTRIBUTING.md).

Made with ❤️ for the OSINT / EASM / CTEM community.
'@

$rel = Invoke-GitHub -Method "Post" -Path "/repos/$REPO/releases" -Body @{
    tag_name         = "v0.1.0"
    target_commitish = "main"
    name             = "v0.1.0"
    body             = $releaseBody
    draft            = $false
    prerelease       = $false
}
if ($rel) {
    Write-Host "   ✅ Release 已创建: $($rel.html_url)" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Release 可能已存在或失败（v0.1.0 已存在可忽略）" -ForegroundColor Yellow
}

# ------------------------------------------------------------
# 2. 创建 M3 / M4 里程碑
# ------------------------------------------------------------
Write-Host "[2/4] 创建里程碑 ..." -ForegroundColor Green

$milestones = @(
    @{
        title       = "M3 社区增长"
        description = "100 Star + awesome-osint 收录 + 首批贡献者"
        due_on      = "2026-09-30T00:00:00Z"
    },
    @{
        title       = "M4 千星目标"
        description = "1000 Star + 企业版部署方案 + 专利提交"
        due_on      = "2026-12-31T00:00:00Z"
    }
)

foreach ($m in $milestones) {
    $created = Invoke-GitHub -Method "Post" -Path "/repos/$REPO/milestones" -Body $m
    if ($created) {
        Write-Host "   ✅ 里程碑已创建: $($created.title)" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  里程碑可能已存在: $($m.title)" -ForegroundColor Yellow
    }
}

# 修复乱码里程碑（旧脚本 ASCII 编码导致中文变 ????）
Write-Host "   🔧 检查并修复乱码里程碑 ..." -ForegroundColor Green
$existing = Invoke-GitHub -Method "Get" -Path "/repos/$REPO/milestones?state=all&per_page=50"
if ($existing) {
    foreach ($m in $milestones) {
        # 按标题前缀匹配（M3 / M4），标题不一致则 PATCH 修正
        $prefix = ($m.title -split " ")[0]
        $match = $existing | Where-Object { $_.title -like "$prefix *" -and $_.title -ne $m.title }
        if ($match) {
            foreach ($ms in $match) {
                $fixed = Invoke-GitHub -Method "Patch" -Path "/repos/$REPO/milestones/$($ms.number)" -Body $m
                if ($fixed) {
                    Write-Host "   ✅ 里程碑已修复: $($ms.title) → $($fixed.title)" -ForegroundColor Green
                }
            }
        }
    }
}

# ------------------------------------------------------------
# 3. 检查 awesome-osint PR #1052 状态
# ------------------------------------------------------------
Write-Host "[3/4] 检查 awesome-osint PR #1052 ..." -ForegroundColor Green
$pr = Invoke-GitHub -Method "Get" -Path "/repos/jivoi/awesome-osint/pulls/1052"
if ($pr) {
    Write-Host "   📌 PR #1052: $($pr.title)" -ForegroundColor Green
    Write-Host "      状态: $($pr.state) | 已合并: $($pr.merged)" -ForegroundColor Green
    if ($pr.merged) {
        Write-Host "      ✅ 已合并！Passive Recon 已收录 awesome-osint" -ForegroundColor Green
    } elseif ($pr.state -eq "closed") {
        # 被关闭但未合并：尝试重新打开（作者可重开自己的 PR）
        Write-Host "      ⏳ 未合并且已关闭，尝试重新打开 ..." -ForegroundColor Yellow
        $reopen = Invoke-GitHub -Method "Patch" -Path "/repos/jivoi/awesome-osint/pulls/1052" -Body @{ state = "open" }
        if ($reopen -and $reopen.state -eq "open") {
            Write-Host "      ✅ 已重新打开: $($reopen.html_url)" -ForegroundColor Green
        } else {
            Write-Host "      ⚠️  重新打开失败（可能需要手动）。" -ForegroundColor Yellow
            Write-Host "        手动打开: https://github.com/jivoi/awesome-osint/pull/1052" -ForegroundColor Yellow
        }
    } else {
        Write-Host "      ⏳ 未合并（state=$($pr.state)）。可在仓库 Discussions 中跟进。" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ⚠️  PR #1052 查询失败（可能已关闭/删除，或网络问题）" -ForegroundColor Yellow
    Write-Host "      手动确认: https://github.com/jivoi/awesome-osint/pulls" -ForegroundColor Yellow
}

# ------------------------------------------------------------
# 4. 创建 GitHub Discussions 公告
# ------------------------------------------------------------
Write-Host "[4/4] 创建 GitHub Discussions 公告 ..." -ForegroundColor Green
$discBody = @'
## 🕵️ What is Passive Recon?

Purely passive OSINT/EASM/CTEM platform — **20 data sources**, one command, zero probes sent to targets.

## ✨ Features

- **20 data sources**: crt.sh, HackerTarget, OTX, URLScan, Wayback, DNSDumpster, CommonCrawl, GitHub, NVD, OSV, Hunter, FOFA, SecurityTrails, Shodan, VirusTotal, ZoomEye, Qichacha, Censys, BinaryEdge
- **Zero-touch**: Never sends a single packet to the target
- **🤖 AI**: domain inference, risk scoring, asset classification, chat query
- **Multi-key rotation**: auto-failover when rate-limited
- **Health monitoring**: auto-degrade unhealthy sources
- **RBAC**: admin/user token roles (enterprise)
- **Compliance report**: periodic audit report
- **Web dashboard**: `python cli.py serve`

## 🚀 Quick Start

````bash
pip install -r requirements.txt
python cli.py collect "Tsinghua University"
````

👉 **GitHub**: https://github.com/TrueFurina/passive-recon
'@

$disc = Invoke-GitHub -Method "Post" -Path "/repos/$REPO/discussions" -Body @{
    title          = "🎉 Passive Recon is live! 20 passive data sources, zero-touch asset discovery"
    body           = $discBody
    category_name  = "Announcements"
}
if ($disc) {
    Write-Host "   ✅ Discussions 公告已创建: $($disc.html_url)" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Discussions API 404：功能未启用，需网页初始化。" -ForegroundColor Yellow
    Write-Host "      1. 打开 https://github.com/TrueFurina/passive-recon/settings" -ForegroundColor Yellow
    Write-Host "      2. 左侧点击 Discussions" -ForegroundColor Yellow
    Write-Host "      3. 点击 'Set up discussions' 启用" -ForegroundColor Yellow
    Write-Host "      4. 启用后重新运行本脚本即可自动创建公告" -ForegroundColor Yellow
    Write-Host "      或手动发布: https://github.com/TrueFurina/passive-recon/discussions" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  ✅ 自动化完成" -ForegroundColor Cyan
Write-Host ""
Write-Host "  剩余需手动（无官方 API）：" -ForegroundColor Yellow
Write-Host "    · 置顶仓库: https://github.com/TrueFurina → Customize your pins" -ForegroundColor Yellow
Write-Host "    · Reddit/HN 推广帖: docs/promotion_drafts.md 复制发布" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""