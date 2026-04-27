# 教材解析流水线 (Material Parsing Pipeline)

> 本文档详细讲解系统如何从一本 PDF 教材出发，最终构建出结构化的知识树（KnowledgeNode + KnowledgeContent），供 Tutor Agent 等下游智能体检索使用。

## 1. 全局流程概览

```
PDF 文件
  │
  ▼
┌─────────────────────────────────────────────────────┐
│  STEP 1: 文本提取与缓存                              │
│  PdfTextExtractor.extract_and_cache()               │
│  → page_list: [(text, tokens), ...]                 │
│  → cache/text_cache/{material_id}/page_XXXX.txt     │
└──────────────────────┬──────────────────────────────┘
                       │
  ┌────────────────────▼──────────────────────────────┐
  │  STEP 2: PageIndex 树构建                          │
  │  page_index_main(page_list=page_list)              │
  │  → tree_result: {structure, toc_text}              │
  └──────────────────────┬──────────────────────────────┘
                       │
  ┌────────────────────▼──────────────────────────────┐
  │  STEP 3: 目录提取（优先PageIndex复用）              │
  │  3-0: build_catalog_from_pageindex()  [零LLM]     │
  │  3a:  extract_catalog_from_page_list() [规则化]    │
  │  3b:  extract_catalog_from_text()     [LLM]       │
  │  3c:  extract_catalog_from_pdf()      [VLM]       │
  └──────────────────────┬──────────────────────────────┘
                       │
  ┌────────────────────▼──────────────────────────────┐
  │  STEP 3.5: 双树映射                                │
  │  map_dual_tree_rule_based()  [规则化, 零LLM]      │
  │  若覆盖率 < 0.8 → map_dual_tree() [LLM fallback]  │
  └──────────────────────┬──────────────────────────────┘
                       │
  ┌────────────────────▼──────────────────────────────┐
  │  STEP 4: 保存到数据库                              │
  │  _parse_and_save_vlm_tree() / _parse_and_save_tree()│
  │  → KnowledgeNode + KnowledgeContent               │
  └─────────────────────────────────────────────────────┘
```

**入口方法**: `TreeBuilderService.ingest_material(material_id, pdf_url_or_path)`  
**文件位置**: `backend/app/services/tree_builder.py`

---

## 2. STEP 1: 文本提取与缓存

**类**: `PdfTextExtractor` (`backend/app/services/pdf_text_extractor.py`)

### 2.1 提取策略（按优先级尝试）

| 优先级 | 方法 | 说明 | 适用场景 |
|--------|------|------|----------|
| 1 | PyMuPDF 直提 | `pymupdf.open()` + `page.get_text()` | 文字版 PDF（最常见） |
| 2 | PyPDF2 直提 | `PyPDF2.PdfReader` + `page.extract_text()` | PyMuPDF 失败时的备选 |
| 3 | EasyOCR | 本地 OCR 引擎，`easyocr.Reader(["ch_sim", "en"])` | 扫描版 PDF |
| 4 | VLM OCR | Kimi-2.5 API 逐页调用 | OCR 质量不佳时的兜底 |

**判断是否需要 OCR**: 若平均每页文本 < 100 字符，认为需要 OCR。

### 2.2 缓存机制

提取结果缓存到 `cache/text_cache/{material_id}/` 目录：
- `page_0001.txt` ~ `page_NNNN.txt`: 逐页文本
- `meta.json`: 元数据（页数、提取方法、token 统计等）

后续 STEP 2~3 直接读取缓存，避免重复提取。

---

## 3. STEP 2: PageIndex 树构建

**入口**: `page_index_main()` (`backend/pageindex/page_index.py`)  
**核心**: `tree_parser()` 函数

### 3.1 完整子流程

```
tree_parser(page_list, opt, doc)
  │
  ├── 1. PDF 类型检测
  │     detect_pdf_type() → "text" 或 "scanned"
  │
  ├── 2. TOC 页检测
  │     find_toc_pages() → [3, 4, 5]  (目录所在页码)
  │
  ├── 3. 目录文本提取
  │     toc_extractor() → toc_content  (拼接目录页文本)
  │
  ├── 4. 页索引检测
  │     detect_page_index() → "yes" / "no"
  │
  ├── 5. TOC 转换为 JSON
  │     toc_transformer() → [{structure, title, page}, ...]
  │
  ├── 6. TOC 验证
  │     verify_toc() → (accuracy, incorrect_results)
  │
  ├── 7. TOC 修复（若验证准确率不足）
  │     fix_incorrect_toc_with_retries() → 修正后的 TOC
  │
  ├── 8. 标题位置检查
  │     check_title_appearance_in_start_concurrent()
  │     → 确定每个章节标题的物理起始页
  │
  ├── 9. 后处理
  │     post_processing() → list_to_tree() → 树结构
  │
  └── 10. 大节点递归细分
        process_large_node_recursively()
```

### 3.2 各环节详解

#### 3.2.1 PDF 类型检测

基于 page_list 的统计特征判断：
- `avg_tokens > 300` 且 `token_diversity < 0.4` → **scanned**（扫描版）
- `noise_count > 50` 且 `avg_tokens < 300` → **scanned**
- 否则 → **text**（文字版）

扫描版 PDF 会走 VLM 图片提取目录的分支。

#### 3.2.2 TOC 页检测 (`find_toc_pages`)

**优化策略**: 规则化优先 + LLM 回退

1. 若 `rule_based_toc_detect=true`，先调用 `find_toc_pages_rule_based()`
   - 在前 20 页中搜索"目录"关键词
   - 进一步检查是否有"第X单元/章/节"等章节模式
   - 连续页检测：若上一页是目录页，当前页也含章节模式，则也标记为目录页
   - **命中时零 LLM 调用**
2. 规则化未命中时，逐页调用 LLM 判断是否为目录页

#### 3.2.3 页索引检测 (`detect_page_index`)

**优化策略**: 规则化优先 + LLM 回退

1. 若 `rule_based_page_index_detect=true`，先调用 `detect_page_index_rule_based()`
   - 逐行匹配 7 种模式：点号+页码、多空格+页码、Tab+页码、章节+页码、作者/页码、单元+页码、独立数字行
   - 匹配率 > 30% 返回 "yes"，0 返回 "no"，否则 "unknown"
2. 返回 "unknown" 时回退到 LLM

#### 3.2.4 TOC 转换 (`toc_transformer`)

将原始目录文本转为结构化 JSON：

```json
{
  "table_of_contents": [
    {"structure": "1", "title": "第一单元", "page": 1},
    {"structure": "1.1", "title": "沁园春·长沙/毛泽东", "page": 2},
    {"structure": "1.2", "title": "立在地球边上放号/郭沫若", "page": 4}
  ]
}
```

- 使用 `toc_transform` profile 的模型（当前为 MiniMax-M2.5）
- 支持续写：当 `finish_reason=max_output_reached` 时，发送续写 prompt 继续生成
- **优化**: 若 `skip_toc_completeness_check=true`，跳过完整性检查 LLM 调用，直接解析 JSON

#### 3.2.5 TOC 验证 (`verify_toc`)

- 随机采样 N 个条目（N = `verify_sample_size`，默认 5）
- 并发调用 `check_title_appearance()` 验证标题是否出现在对应页面
- 返回 (accuracy, incorrect_results)

#### 3.2.6 TOC 修复 (`fix_incorrect_toc_with_retries`)

- 最多重试 `fix_max_attempts`（默认 2）次
- 每次调用 LLM 修复错误条目
- 若错误数不再减少则提前停止

#### 3.2.7 标题位置检查 (`check_title_appearance_in_start_concurrent`)

**优化策略**: 规则化优先 + LLM 回退

1. 若 `rule_based_title_check=true`，先调用 `check_title_in_start_rule_based()`
   - 取页面前 200 字符，检查标题是否出现在开头
   - 支持精确匹配、去空格匹配
   - 前缀模糊匹配（标题前 4 字符匹配但整体不匹配）返回 None，回退 LLM
2. 仅对规则化无法确定的条目调用 LLM

#### 3.2.8 摘要生成 (`generate_summaries_batch`)

**优化**: 批量摘要生成
- 将节点按 `batch_size`（默认 6）分组
- 每组一次 LLM 调用生成所有摘要
- 调用次数从 N 降为 ceil(N/6)

### 3.3 处理模式选择

根据 TOC 情况，`meta_processor()` 选择不同处理模式：

| 模式 | 触发条件 | 说明 |
|------|----------|------|
| `process_toc_with_page_numbers` | TOC 有页码 | 最常见，按页码定位章节 |
| `process_toc_no_page_numbers` | TOC 无页码 | 需要通过标题匹配定位 |
| `process_no_toc` | 无 TOC | 按页逐段分析 |

若验证准确率不足，按 `with_page_numbers → no_page_numbers → no_toc` 降级。

---

## 4. STEP 3: 目录提取

### 4.1 优先级链

```
3-0: build_catalog_from_pageindex()  ← 优先，零 LLM
  │
  ├─ 返回非空列表 → 直接使用 catalog_tree
  ├─ 返回 _NEED_TOC_TEXT_PARSE → 仅执行 3b
  └─ 返回空列表 → 继续尝试 3a/3b/3c
      │
      3a: extract_catalog_from_page_list()  ← 规则化解析
      │
      3b: extract_catalog_from_text()       ← LLM 文本解析
      │
      3c: extract_catalog_from_pdf()        ← VLM 图片提取
```

### 4.2 `build_catalog_from_pageindex()` 详解

**核心思想**: PageIndex 已经构建了文档结构树（STEP 2 的输出），目录信息已经隐含在 structure 中，无需再次调用 LLM 提取。

**逻辑**:
1. 递归将 PageIndex 节点转为 `{title, page, children}` 格式
2. 若 structure 节点数 >= 5，直接返回 catalog_tree
3. 若节点数 < 5 但有 toc_text，返回 `_NEED_TOC_TEXT_PARSE` 标记（仅用 LLM 解析 toc_text）
4. 否则返回空列表（触发完整 fallback 链）

### 4.3 三级 Fallback

| 级别 | 方法 | LLM 调用 | 说明 |
|------|------|----------|------|
| 3a | `extract_catalog_from_page_list()` | 0 或少量 | 规则化解析目录页文本，支持 3 种目录格式 |
| 3b | `extract_catalog_from_text()` | 1 次 | 用 fast 模型解析原始 TOC 文本为层级 JSON 树 |
| 3c | `extract_catalog_from_pdf()` | 1~2 次 | VLM 读取 PDF 前几页图片提取目录 |

---

## 5. STEP 3.5: 双树映射

### 5.1 为什么需要双树映射？

系统存在两棵树：
- **PageIndex 树 (structure)**: STEP 2 构建，基于文档物理结构，节点有 `node_id`、`physical_index`、`start_index`/`end_index`
- **目录树 (catalog_tree)**: STEP 3 构建，基于人类可读的目录层级，节点有 `title`、`page`、`children`

双树映射将目录树的每个节点关联到 PageIndex 树的对应节点，使得：
- 目录树提供人类可读的章节结构
- PageIndex 树提供精确的页码范围和内容定位

### 5.2 规则化映射 (`map_dual_tree_rule_based`)

**零 LLM 调用**，基于页码范围 + 标题相似度：

1. **扁平化 PI 树**: 将 PageIndex 树展平为节点列表
2. **构建页码范围映射**: 每个目录节点的页码 → 允许的 PI node_id 集合
3. **估算页码偏移**: 找到目录页码 → PI physical_index 的最佳对齐偏移
4. **递归映射**: 对每个目录节点：
   - 根据页码范围筛选候选 PI 节点
   - 计算标题 Jaccard bigram 相似度（阈值 > 0.3）
   - 按相似度降序排列，取所有匹配
5. **计算覆盖率**: 已映射 PI 节点数 / 总 PI 节点数

### 5.3 LLM Fallback (`map_dual_tree`)

当规则化映射覆盖率 < 0.8（阈值可配置）时触发：
- 构建 LLM prompt，包含 PI 节点列表和目录树
- 调用 fast 模型进行映射
- 后处理: 移除违反页码约束的映射

---

## 6. STEP 4: 数据库保存

### 6.1 两条保存路径

| 路径 | 触发条件 | 方法 | 特点 |
|------|----------|------|------|
| VLM 树保存 | 双树映射成功 | `_parse_and_save_vlm_tree()` | 节点有 `mapped_pi_nodes`，内容从 PI map 获取 |
| 原始树保存 | 未使用目录树 | `_parse_and_save_tree()` | 节点有 `pageindex_ref`，1:1 映射 PI 节点 |

### 6.2 数据模型

```
KnowledgeNode (知识节点 - 骨架)
  ├── id: UUID
  ├── material_id: FK → Material
  ├── parent_id: FK → KnowledgeNode (自引用树)
  ├── title: str           # 章节标题，如"第一单元"
  ├── level: int           # 树深度: 1=单元, 2=课文, 3=子项
  ├── seq_num: int         # 同级排序号
  ├── pageindex_ref: str   # 直接映射的 PI node_id (仅原始树)
  ├── mapped_pi_nodes: list # 映射的 PI node_id 列表
  └── pi_nodes_json: list  # PI 节点元数据 (不含 text/children)

KnowledgeContent (知识内容 - 血肉)
  ├── id: UUID
  ├── knowledge_node_id: FK → KnowledgeNode
  ├── pi_node_id: str      # 来源 PI 节点
  └── content_md: str      # Markdown 格式内容
```

**骨肉分离设计**: KnowledgeNode 只存结构索引（轻量），KnowledgeContent 存富文本正文。检索时先定位 Node，再按需取回 Content。

---

## 7. LLM 优化体系

### 7.1 优化策略: 规则化优先 + LLM 回退

核心思想：**能用正则/模式匹配解决的，不调用 LLM；规则不确定时才回退到 LLM**。

### 7.2 九项优化配置

| # | 优化点 | 配置项 | 默认值 | 节省 LLM 调用 |
|---|--------|--------|--------|---------------|
| 1 | 规则化目录页检测 | `rule_based_toc_detect` | true | ~20次/页 |
| 2 | 规则化页索引检测 | `rule_based_page_index_detect` | true | 1次 |
| 3 | 规则化标题检查 | `rule_based_title_check` | true | ~5-10次 |
| 4 | 跳过TOC完整性检查 | `skip_toc_completeness_check` | true | ~5-10次 |
| 5 | 验证采样缩减 | `verify_sample_size` | 5 | ~N-5次 |
| 6 | 修复重试限制 | `fix_max_attempts` | 2 | ~1轮 |
| 7 | 批量摘要生成 | `summary_batch_size` | 6 | ~N*5/6次 |
| 8 | PageIndex结果复用 | (自动) | - | ~3-5次 |
| 9 | 规则化双树映射 | `rule_based_dual_tree_map` | true | 1次 |

**综合效果**: LLM 调用从优化前约 120 次降至约 15-30 次，减少 75-87%。

### 7.3 规则化函数详解

三个规则化函数位于 `backend/pageindex/rule_based.py`：

#### `find_toc_pages_rule_based(page_list, max_check_pages=20)`

- 搜索关键词: "目录", "目  录", "目次", "CONTENTS", "Contents", "contents"
- 检测模式: "第X章/节/单元/课/组"、点号+页码、数字编号
- 连续页检测: 上一页是目录页时，当前页也检查章节模式

#### `detect_page_index_rule_based(toc_content)`

- 7 种匹配模式:
  - 点号+页码: `标题...12`
  - 4+空格+页码: `标题    12`
  - Tab+页码: `标题\t12`
  - 章节+页码: `第1章 xxx 12`
  - 作者/页码: `标题/作者 12`
  - 单元+页码: `第二单元 31`
  - 独立数字行: `^\s*\d{1,4}\s*$`
- 匹配率 > 30% → "yes"，0 → "no"，否则 → "unknown"

#### `check_title_in_start_rule_based(title, page_text, max_check_chars=200)`

- 清洗标题中的异常空格（CJK 字符间空格去除）
- 精确匹配 → "yes"
- 去空格匹配 → "yes"
- 前缀模糊（前 4 字符匹配但整体不匹配）→ None（回退 LLM）
- 都不匹配 → "no"

---

## 8. 模型配置

### 8.1 分层模型架构

| 层级 | 用途 | 当前模型 | 典型任务 |
|------|------|----------|----------|
| fast | 简单判断/检测 | MiniMax-M2.5 | TOC 检测、标题检查、页索引检测 |
| medium | 中等复杂度转换 | MiniMax-M2.5 | TOC 转换、节点摘要 |
| heavy | 复杂生成/推理 | MiniMax-M2.7 | TOC 生成、TOC 修复 |
| vision | 图片理解/VLM | MiniMax-M2.7 | 扫描版 PDF 目录提取 |

### 8.2 任务-模型映射

| 任务 | 模型层级 | max_tokens | temperature |
|------|----------|------------|-------------|
| toc_detect | fast | 2000 | 0 |
| title_check | fast | 2000 | 0 |
| page_index_detect | fast | 2000 | 0 |
| toc_transform | medium | 16000 | 0 |
| node_summary | medium | 500 | 0.3 |
| toc_generate | heavy | 32000 | 0 |
| toc_fix | heavy | 2000 | 0 |

### 8.3 API 配置

当前使用 MiniMax 的 Anthropic 兼容 API：
- `ANTHROPIC_API_KEY`: MiniMax API Key
- `ANTHROPIC_BASE_URL`: `https://api.minimaxi.com/anthropic`
- MiniMax-M2.5 为 thinking 模型，会返回 thinking + text 两个 block

---

## 9. 配置文件

所有配置位于 `backend/pageindex/config.yaml`：

```yaml
# 模型配置
model: "minimax"
model_profiles:
  fast: "MiniMax-M2.5"
  medium: "MiniMax-M2.5"
  heavy: "MiniMax-M2.7"

# 任务-模型映射
task_to_profile:
  toc_detect: fast
  title_check: fast
  page_index_detect: fast
  toc_transform: medium
  node_summary: medium
  toc_generate: heavy
  toc_fix: heavy

# 流程控制
toc_check_page_num: 20        # TOC 检测最大页数范围
max_page_num_each_node: 10    # 每个节点最大页数
if_add_node_summary: "yes"    # 是否生成摘要
if_add_node_text: "no"        # 是否添加节点文本

# LLM 优化配置
rule_based_toc_detect: true              # 规则化 TOC 页检测
rule_based_page_index_detect: true       # 规则化页索引检测
rule_based_title_check: true             # 规则化标题检查
rule_based_dual_tree_map: true           # 规则化双树映射
skip_toc_completeness_check: true        # 跳过 TOC 完整性检查
verify_sample_size: 5                    # 验证采样数量
fix_max_attempts: 2                      # 修复最大重试次数
summary_batch_size: 6                    # 批量摘要批大小
dual_tree_map_coverage_threshold: 0.8    # 双树映射覆盖率阈值
```

---

## 10. 解析结果示例

以《普通高中教科书·语文必修 上册》（154 页）为例：

### 10.1 解析结果

| 指标 | 值 |
|------|-----|
| KnowledgeNodes 总数 | 62 |
| Level 1（单元） | 8 个 |
| Level 2（课文/节） | 44 个 |
| Level 3（子项） | 10 个 |
| KnowledgeContents | 2 条（因 if_add_node_text=no） |

### 10.2 知识树结构

```
第一单元
  ├── 沁园春·长沙/毛泽东
  ├── 立在地球边上放号/郭沫若
  ├── 红烛/闻一多
  ├── * 峨日朵雪峰之侧/昌耀
  ├── * 致云雀/雪莱
  ├── 百合花/茹志鹃
  ├── * 哦，香雪/铁凝
  └── 单元学习任务

第二单元
  ├── 喜看稻菽千重浪——记首届国家最高科技奖获得者袁隆平/沈英甲
  ├── * 心有一团火，温暖众人心/林为民
  ├── ...

第八单元
  ├── 词语积累与词语解释
  ├── 学习活动
  │   ├── 丰富词语积累
  │   ├── 把握古今词义的联系与区别
  │   └── 词义的辨析和词语的使用
  └── 古诗词诵读
      ├── 静女/《诗经·邶风》
      ├── 涉江采芙蓉/《古诗十九首》
      ├── 虞美人（春花秋月何时了）/李煜
      └── 鹊桥仙（纤云弄巧）/秦观
```

### 10.3 优化效果

| 优化点 | 效果 |
|--------|------|
| 规则化目录页检测 | 命中，直接检测到 3 个 TOC 页，省 ~20 次 LLM |
| 规则化页索引检测 | 命中（增强后），省 1 次 LLM |
| 跳过完整性检查 | 生效，省 ~5-10 次 LLM |
| PageIndex 结果复用 | 生效，catalog_tree 直接构建，省 ~3-5 次 LLM |
| 规则化双树映射 | 生效，62 个节点全部规则映射，省 1 次 LLM |

---

## 11. 关键文件索引

| 文件 | 职责 |
|------|------|
| `app/services/tree_builder.py` | 主入口 `ingest_material()`，STEP 3~4 编排 |
| `app/services/pdf_text_extractor.py` | STEP 1 文本提取与缓存 |
| `pageindex/page_index.py` | STEP 2 PageIndex 树构建全流程 |
| `pageindex/rule_based.py` | 三个规则化优化函数 |
| `pageindex/utils.py` | LLM 调用封装、批量摘要、LLMCallTracker |
| `pageindex/config.yaml` | 所有配置项 |
| `app/utils/vlm_catalog.py` | 目录提取、双树映射（规则化 + LLM） |
| `app/utils/llm_router.py` | 模型分层路由 |
| `app/models/material.py` | KnowledgeNode / KnowledgeContent ORM 模型 |
