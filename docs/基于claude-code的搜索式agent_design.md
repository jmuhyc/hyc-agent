# 项目代码搜索功能实现分析报告

## 一、概述

本项目采用**无第三方搜索引擎依赖**的搜索架构，完全基于：
- **ripgrep** 作为内容搜索核心
- **原生 TypeScript 实现的 FileIndex** 作为模糊文件搜索
- **glob 模式匹配** 作为文件名搜索

---

## 二、核心文件清单

### 2.1 搜索核心文件

| 文件路径 | 功能 | 关键类/函数 |
|---------|------|------------|
| `src/tools/GrepTool/GrepTool.ts` | 正则表达式内容搜索 | `GrepTool` |
| `src/tools/GlobTool/GlobTool.ts` | 文件名模式匹配 | `GlobTool` |
| `src/native-ts/file-index/index.ts` | 模糊文件搜索（fzf/nucleo风格） | `FileIndex` |
| `src/utils/ripgrep.ts` | ripgrep 封装层 | `ripGrep()`, `ripGrepStream()` |
| `src/utils/glob.ts` | glob 模式匹配封装 | `glob()` |
| `src/components/GlobalSearchDialog.tsx` | 全局搜索 UI（Ctrl+Shift+F） | `GlobalSearchDialog` |
| `src/utils/toolSearch.ts` | MCP 工具搜索发现 | `ToolSearchTool` |
| `src/utils/transcriptSearch.ts` | 历史记录搜索 | `transcriptSearch` |
| `src/utils/codeIndexing.ts` | 第三方索引工具检测 | `detectCodeIndexingTool()` |

### 2.2 辅助文件

| 文件路径 | 功能 |
|---------|------|
| `src/query.ts` | 查询引擎核心 |
| `src/QueryEngine.ts` | 查询引擎配置和执行 |
| `src/ink/hooks/use-search-highlight.ts` | 搜索高亮 Hook |

---

## 三、架构设计

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                               │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │ GlobalSearchDialog  │    │      Tool Use API               │ │
│  │  (Ctrl+Shift+F)     │    │   GrepTool / GlobTool / ...     │ │
│  └─────────────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        搜索工具层                                │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │   GrepTool    │  │   GlobTool    │  │  ToolSearchTool     │  │
│  │  (内容搜索)    │  │  (文件查找)    │  │  (MCP工具发现)       │  │
│  └───────────────┘  └───────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                       索引/搜索引擎层                             │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐  │
│  │        ripgrep           │  │        FileIndex           │  │
│  │   (正则表达式内容搜索)     │  │  (模糊文件搜索 nucleo 风格)   │  │
│  │  system / builtin /      │  │  O(1) 位图过滤              │  │
│  │  embedded 三种模式        │  │  Top-k 贪心匹配             │  │
│  └──────────────────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 搜索模式对比

| 搜索类型 | 实现方式 | 入口 | 支持特性 |
|---------|---------|------|---------|
| **内容搜索** | ripgrep | GrepTool | 正则、上下文、多种输出模式 |
| **文件搜索** | ripgrep --files + glob | GlobTool | glob 模式、修改时间排序 |
| **模糊文件搜索** | FileIndex (TS) | 内部使用 | 大小写不敏感、CamelCase 加分 |
| **全局 UI 搜索** | ripgrep stream | GlobalSearchDialog | 流式、实时、100ms 防抖 |
| **工具发现** | ToolSearchTool | MCP | 动态加载、token 阈值 |

---

## 四、核心实现详解

### 4.1 ripgrep 封装层

**文件**: `src/utils/ripgrep.ts`

```typescript
// 三种运行模式
export type RipgrepMode = 'system' | 'builtin' | 'embedded'

// system: 使用系统安装的 ripgrep
// builtin: 使用 vendor/ripgrep/ 中的二进制
// embedded: 使用 Bun 内置的 ripgrep
```

**核心函数**:

```typescript
// 单次搜索
export async function ripGrep(
  args: string[],           // ripgrep 参数
  target: string,           // 搜索目标路径
  abortSignal: AbortSignal // 中止信号
): Promise<string[]>

// 流式搜索（用于 UI 实时显示）
export async function ripGrepStream(
  args: string[],
  target: string,
  abortSignal: AbortSignal,
  onLines: (lines: string[]) => void
): Promise<void>
```

**关键特性**:
- 支持超时处理（WSL 60s，其他 20s），**可通过环境变量 `CLAUDE_CODE_GLOB_TIMEOUT_SECONDS` 配置**
- EAGAIN 错误自动重试（单线程模式）
- SIGTERM + SIGKILL 信号处理（SIGTERM 5秒后未响应则升级为 SIGKILL）
- 20MB stdout 缓冲限制
- **使用 spawn（embedded 模式）和 execFile（system/builtin 模式）两种调用方式**
- 支持 `codesign` 对 macOS 内置 ripgrep 进行签名验证

---

### 4.2 GrepTool 内容搜索

**文件**: `src/tools/GrepTool/GrepTool.ts`

**输入 Schema**:
```typescript
{
  pattern: string,              // 正则表达式模式
  path?: string,                // 搜索路径
  glob?: string,                // 文件过滤模式
  output_mode: 'content' | 'files_with_matches' | 'count',
  context?: { before?: number, after?: number },  // 上下文行数
  head_limit?: number,          // 结果上限（默认 250）
  multiline?: boolean,
  case_sensitive?: boolean,
  inverse?: boolean,            // 反向匹配
  offset?: number,              // 结果偏移
}
```

**输出 Schema**:
```typescript
{
  mode: 'content' | 'files_with_matches' | 'count',
  numFiles: number,
  filenames: string[],
  content?: string,            // content 模式：多行用 \n 连接
  numLines?: number,
  numMatches?: number,
  appliedLimit?: number,
  appliedOffset?: number,
}
```

**实现流程**:
```
GrepTool.call()
    │
    ├── expandPath() 解析绝对路径
    │
    ├── 构建 ripgrep 参数
    │   ├── --hidden 包含隐藏文件
    │   ├── --glob !.git 排除 VCS 目录
    │   ├── --max-columns 500 限制行长度
    │   └── -l/-c/-n 根据 output_mode 设置
    │
    ├── ripGrep() 执行搜索
    │
    └── 处理结果
        ├── content: 转换相对路径，限制行数
        ├── files_with_matches: 按 mtime 排序
        └── count: 解析总匹配数和文件数
```

---

### 4.3 GlobTool 文件搜索

**文件**: `src/tools/GlobTool/GlobTool.ts`

**输入 Schema**:
```typescript
{
  pattern: string,    // glob 模式（如 **/*.ts）
  path?: string,      // 搜索目录
}
```

**输出 Schema**:
```typescript
{
  durationMs: number,
  numFiles: number,
  filenames: string[],
  truncated: boolean,
}
```

**实现**: 使用 `glob()` 函数（内部封装了文件系统遍历），返回文件路径数组，按修改时间排序，默认限制 100 个结果（通过 `globLimits.maxResults` 配置）。

---

### 4.4 FileIndex 模糊文件搜索

**文件**: `src/native-ts/file-index/index.ts`

**核心数据结构**:
```typescript
export class FileIndex {
  private paths: string[] = []                    // 原始路径数组
  private lowerPaths: string[] = []               // 小写版本（大小写不敏感）
  private charBits: Int32Array = new Int32Array(0) // a-z 位图（O(1) 快速过滤）
  private pathLens: Uint16Array = new Uint16Array(0) // 路径长度数组
  private topLevelCache: SearchResult[] | null = null // 顶层目录缓存
  private readyCount: number = 0                  // 异步构建时已索引的路径数
}
```

**索引构建**:
- `loadFromFileListAsync()`: 异步构建索引，每 ~8-12k 路径让出一次控制权
- `CHUNK_MS = 4`: 每 4ms 异步工作量后让出控制权
- `MAX_QUERY_LEN = 64`: 最大查询长度
- `TOP_LEVEL_CACHE_LIMIT = 100`: 顶层目录缓存大小

**搜索算法**:

1. **O(1) 位图过滤**
   - 预计算每个路径的字符位图（a-z 26个字母）
   - 查询时构建 needle 位图
   - `charBits[i] & needleBitmap === needleBitmap` 快速排除不含所有查询字符的路径

2. **贪心最早匹配 (Greedy-earliest)**
   - 对每个路径，找到查询字符最早出现位置
   - 越早匹配得分越高

3. **边界/CamelCase 加分常量**
   - `SCORE_MATCH = 16`（每匹配一个字符）
   - `BONUS_BOUNDARY = 8`（匹配单词边界）
   - `BONUS_CAMEL = 6`（匹配 CamelCase 边界）
   - `BONUS_CONSECUTIVE = 4`（连续匹配）
   - `BONUS_FIRST_CHAR = 8`（首字符匹配）
   - `PENALTY_GAP_START = 3`（字符间隔起始惩罚）
   - `PENALTY_GAP_EXTENSION = 1`（间隔扩展惩罚）

4. **Top-k 优化**
   - 维护大小为 limit 的最小堆（按 fuzzScore 升序）
   - 避免全量排序

5. **结果排序**
   - topK 升序排列后反转（最佳结果在前）
   - 最终得分 = 位置得分 × 1.05（如果路径包含 "test"），上限 1.0
   - **注意：得分越低越好（0 为最佳匹配）**

```typescript
search(query: string, limit: number): SearchResult[] {
  // 1. 空查询 → 返回顶层缓存
  if (!query) return this.topLevelCache.slice(0, limit)

  // 2. 大小写检测
  const hasUpperCase = /[A-Z]/.test(query)

  // 3. 构建 needle 位图
  const needleBitmap = this.buildNeedleBitmap(query)

  // 4. Top-k 搜索循环
  const topK: { path: string; fuzzScore: number }[] = []
  for (const path of this.paths) {
    // O(1) 位图快速过滤
    if ((charBits[i]! & needleBitmap) !== needleBitmap) continue

    // 贪心匹配 + 评分
    const score = this.scorePath(path, query, posBuf)
    topK.push({ path, fuzzScore: score })
  }

  // 5. 排序返回
  return topK.sort((a, b) => b.fuzzScore - a.fuzzScore).slice(0, limit)
}
```

---

### 4.5 GlobalSearchDialog UI

**文件**: `src/components/GlobalSearchDialog.tsx`

**快捷键**: `Ctrl+Shift+F` / `Cmd+Shift+F`

**搜索流程**:
```
用户输入查询
    │
    ├── 100ms 防抖
    │
    ├── ripGrepStream() 流式搜索
    │   - 最多 MAX_MATCHES_PER_FILE (10) 每文件
    │   - 最多 MAX_TOTAL_MATCHES (500) 总计
    │
    ├── 解析结果 "path:line:text"
    │   - Windows 路径处理（正则 `^(.*?):(\d+):(.*)$`）
    │
    └── 显示预览 + 高亮匹配
```

---

## 五、搜索入口点汇总

| 入口 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `GrepTool` | 工具调用 | `src/tools/GrepTool/GrepTool.ts:160` | 通过 Tool Use API 调用 |
| `GlobTool` | 工具调用 | `src/tools/GlobTool/GlobTool.ts:57` | 通过 Tool Use API 调用 |
| `GlobalSearchDialog` | UI 快捷键 | `src/components/GlobalSearchDialog.tsx` | Ctrl+Shift+F |
| `ToolSearchTool` | 工具发现 | `src/tools/ToolSearchTool/ToolSearchTool.ts` | MCP 工具动态发现 |
| `transcriptSearch` | 工具调用 | `src/utils/transcriptSearch.ts` | 历史记录搜索 |

---

## 六、结果处理机制

### 6.1 路径处理
- 绝对路径转换为相对路径（节省 token）
- 基于 `getCwd()` 计算相对路径
- VCS 目录（`.git`, `.svn` 等）自动排除

### 6.2 结果限制

| 工具 | 默认限制 | 可配置 |
|------|---------|--------|
| GrepTool | 250 (`DEFAULT_HEAD_LIMIT`) | `head_limit` 参数 |
| GlobTool | 100 | `limit` 参数 |
| GlobalSearchDialog | 500 总计, 10/文件 | `MAX_TOTAL_MATCHES`, `MAX_MATCHES_PER_FILE` |

### 6.3 结果截断处理

```typescript
function applyHeadLimit<T>(
  items: T[],
  limit: number | undefined,
  offset: number = 0,
): { items: T[]; appliedLimit: number | undefined } {
  const effectiveLimit = limit ?? DEFAULT_HEAD_LIMIT
  return {
    items: items.slice(offset, offset + effectiveLimit),
    appliedLimit: wasTruncated ? effectiveLimit : undefined,
  }
}
```

---

## 七、第三方工具检测

**文件**: `src/utils/codeIndexing.ts`

检测项目中是否存在以下第三方代码索引工具，用于遥测：

```typescript
export type CodeIndexingTool =
  | 'sourcegraph'
  | 'cody'
  | 'aider'
  | 'continue'
  | 'github-copilot'
  | 'cursor'
  | 'tabby'
  | 'windsurf'
  | 'devin'
  | 'junie'
  | 'fig'
  | 'loopy'
  | 'vscode-builtin-search'
```

---

## 八、完整搜索流程图

### 8.1 GrepTool 完整流程

```
用户输入 pattern
    │
    ▼
GrepTool.call({ pattern, path, glob, output_mode, ... })
    │
    ▼
expandPath() 解析绝对路径
    │
    ▼
构建 ripgrep 参数
┌──────────────────────────────────────┐
│ - --hidden 包含隐藏文件              │
│ - --glob !.git 排除 VCS 目录         │
│ - --max-columns 500 限制行长度       │
│ - -l/-c/-n 根据 output_mode         │
│ - --context before/after             │
│ - -i/-s/-S 大小写模式                │
│ - -v 反向匹配                        │
└──────────────────────────────────────┘
    │
    ▼
ripGrep() 执行搜索
┌──────────────────────────────────────┐
│ - 支持超时（WSL 60s，其他 20s）       │
│ - AbortController 支持取消           │
│ - EAGAIN 自动重试（单线程模式）       │
└──────────────────────────────────────┘
    │
    ▼
处理结果
┌──────────────────────────────────────┐
│ content 模式:                        │
│   - 绝对路径 → 相对路径               │
│   - 限制行数（DEFAULT_HEAD_LIMIT=250）│
│   - 添加 appliedLimit/appliedOffset  │
│                                       │
│ files_with_matches 模式:              │
│   - 按 mtime 排序                     │
│                                       │
│ count 模式:                          │
│   - 解析总匹配数 numMatches           │
│   - 解析匹配文件数 numFiles           │
└──────────────────────────────────────┘
    │
    ▼
返回结果
{
  mode: 'content' | 'files_with_matches' | 'count',
  numFiles: number,
  filenames: string[],
  content?: string[],
  numLines?: number,
  numMatches?: number,
  appliedLimit?: number,
  appliedOffset?: number,
}
```

### 8.2 FileIndex 模糊搜索流程

```
FileIndex.loadFromFileList(fileList)
    │
    ├── 去重 + 过滤空字符串
    │
    └── buildIndex(paths)
        ├── 重置数组 (paths, lowerPaths, charBits, pathLens)
        ├── 预计算顶层目录缓存 (topLevelCache)
        └── 索引每个路径
            - lowerPaths[i] = path.toLowerCase()
            - charBits[i] = 预计算的 a-z 位图

search(query, limit)
    │
    ├── 空查询 → 返回 topLevelCache.slice(0, limit)
    │
    ├── 大小写检测
    │   - hasUpperCase = /[A-Z]/.test(query)
    │
    ├── 构建 needleBitmap
    │   - query 中的每个字符映射到位图的对应 bit
    │
    ├── Top-k 搜索循环
    │   ├── O(1) 位图过滤
    │   │   └── if ((charBits[i] & needleBitmap) !== needleBitmap) continue
    │   │
    │   ├── 贪心最早匹配
    │   │   └── indexOf(needle, posBuf)
    │   │
    │   ├── 边界/CamelCase 评分
    │   │   └── scoreBonusAt(path, pos, isBoundary)
    │   │
    │   └── 维护 Top-k 数组
    │       └── 插入排序，保持 k 个最佳结果
    │
    └── 排序返回
        ├── 按 fuzzScore 降序排列
        └── "test" 路径加 1.05× 惩罚（避免误匹配）
```

---

## 九、技术总结

| 维度 | 实现方案 |
|------|---------|
| **内容搜索** | ripgrep - 正则表达式，高性能，支持多种输出模式 |
| **文件搜索** | `glob()` 函数封装，支持 glob 模式匹配 |
| **模糊文件搜索** | 原生 TypeScript 实现（nucleo/fzf 风格算法） |
| **搜索 UI** | GlobalSearchDialog - Ctrl+Shift+F 唤起，流式实时显示 |
| **工具发现** | ToolSearchTool - 动态 MCP 工具加载，token 阈值控制 |
| **第三方依赖** | **无** - ripgrep 为内置或 vendored，无外部搜索引擎 |
| **结果限制** | GrepTool 250，GlobTool 100，UI 500 |
| **性能优化** | 流式处理、Top-k 算法、O(1) 位图过滤、贪心匹配、异步分块索引 |
| **路径处理** | 绝对→相对转换，VCS 目录自动排除 |
| **超时控制** | WSL 60s，其他 20s，**可通过 `CLAUDE_CODE_GLOB_TIMEOUT_SECONDS` 环境变量配置** |
| **安全特性** | UNC 路径跳过文件系统操作（防止 NTLM 凭据泄露）、PATH 劫持防护（使用命令名 'rg' 而非系统路径） |

---