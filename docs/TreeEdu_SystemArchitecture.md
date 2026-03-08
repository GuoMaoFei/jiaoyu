# 智树 (TreeEdu) Agent - 系统架构设计 (System Architecture)

> **文档状态**：V1.0 架构终稿 | **更新日期**：2026-02-25

---

## 1. 系统全景架构 (System Overview)

下图展示了智树系统从终端用户到底层基础设施的完整分层架构。

```mermaid
graph TB
    subgraph Clients["🖥️ 接入层 (Client Layer) — 响应式 Web/PWA"]
        direction LR
        SP["👩‍🎓 Student Portal<br/>PC · Pad · Mobile H5"]
        PP["👨‍👩‍👧 Parent Portal<br/>Web 仪表盘"]
        AP["🔧 Admin Dashboard<br/>PC 端运维"]
    end

    subgraph Gateway["🌐 网关与通信层 (API Gateway & Realtime)"]
        direction LR
        REST["REST API<br/>(FastAPI)"]
        WS["WebSocket / SSE<br/>(流式对话)"]
        AUTH["Auth & RBAC<br/>(JWT / OAuth2)"]
    end

    subgraph BizLayer["⚙️ 业务中台 (Business Logic Layer)"]
        direction TB
        subgraph AgentOrch["🤖 Agent 编排层"]
            SO["Socratic Orchestrator<br/>苏格拉底对话编排"]
            GL["Guided Learning Controller<br/>引导学习控制器"]
            AR["Adaptive Router<br/>自适应路由引擎"]
        end
        subgraph BizServices["📦 业务服务层"]
            PS["Plan Service<br/>学习计划管理"]
            TS["Test Service<br/>组卷 & 批改"]
            MS["Mistake Service<br/>错题管理"]
            RS["Report Service<br/>家长周报生成"]
            BS["Bookshelf Service<br/>书架管理"]
        end
    end

    subgraph CoreEngines["🧠 AI 核心引擎层 (Core AI Engines)"]
        direction LR
        VCM["👁️ V-Catalog Engine<br/>视觉提取引擎<br/>· 截取排版提取真实目录"]
        TIE["🌳 Tree-Index Engine<br/>树状索引引擎<br/>· PageIndex 黑盒切树<br/>· Dual-Tree 语义关联映射"]
        DRE["🗺️ Dynamic Routing Engine<br/>动态规划引擎<br/>· 基准计划生成<br/>· 每日任务调度"]
        SQE["💬 Socratic QA Engine<br/>苏格拉底问答引擎<br/>· 启发式对话<br/>· 树内限定作答"]
        VGE["🎲 Variant Gen Engine<br/>变式生成引擎<br/>· 同考点换皮<br/>· 难度可控出题"]
        EME["❤️ Empathy Engine<br/>共情与鼓励引擎<br/>· 情绪状态监控<br/>· 正向强化干预"]
    end

    subgraph Foundation["🏗️ 基础设施层 (Infrastructure Layer)"]
        direction LR
        LLM["🤖 大模型网关<br/>GPT-4o / Gemini<br/>多模态推理"]
        PIX["📚 PageIndex<br/>无向量树状 RAG<br/>知识树检索"]
        PG["🐘 PostgreSQL<br/>关系型数据库<br/>+ JSONB 文档"]
        OSS["☁️ 对象存储 (OSS)<br/>图片 / PDF<br/>媒体资源"]
        CACHE["⚡ Redis<br/>会话缓存<br/>计划热数据"]
    end

    Clients --> Gateway
    Gateway --> BizLayer
    BizLayer --> CoreEngines
    CoreEngines --> Foundation

    style Clients fill:#E8F5E9,stroke:#4CAF50,stroke-width:2px
    style Gateway fill:#E3F2FD,stroke:#2196F3,stroke-width:2px
    style BizLayer fill:#FFF3E0,stroke:#FF9800,stroke-width:2px
    style CoreEngines fill:#F3E5F5,stroke:#9C27B0,stroke-width:2px
    style Foundation fill:#ECEFF1,stroke:#607D8B,stroke-width:2px
```

---

## 2. 核心引擎协作拓扑 (Engine Collaboration Topology)

五大核心引擎并非各自为战，而是在不同学习场景下形成特定的**协作编排模式**。

```mermaid
flowchart LR
    subgraph Input["📥 输入触发源"]
        U1["学生选课学习"]
        U2["学生拍题提问"]
        U3["每日登录打卡"]
        U4["发起阶段自测"]
    end

    TIE["🌳 Tree-Index<br/>Engine"]
    DRE["🗺️ Dynamic Routing<br/>Engine"]
    SQE["💬 Socratic QA<br/>Engine"]
    VGE["🎲 Variant Gen<br/>Engine"]
    EME["❤️ Empathy<br/>Engine"]

    subgraph Output["📤 输出结果"]
        O1["📖 结构化课程讲解"]
        O2["🔍 知识定位 + 启发回答"]
        O3["📋 每日学习任务"]
        O4["📝 定制化试卷"]
    end

    U1 --> TIE --> SQE --> O1
    U2 --> TIE --> SQE --> O2
    U3 --> DRE --> VGE --> O3
    U4 --> TIE --> VGE --> O4

    SQE -.->|情绪监控| EME
    DRE -.->|状态不佳时降级| EME
    EME -.->|干预信号| DRE

    style Input fill:#E8F5E9,stroke:#4CAF50
    style Output fill:#E3F2FD,stroke:#2196F3
```

---

## 3. 数据流架构 (Data Flow Architecture)

系统最核心的数据闭环：**学习 → 评估 → 沉淀 → 再规划**。

```mermaid
flowchart TD
    subgraph LearnLoop["🔄 核心学习闭环"]
        A["📘 选择教材<br/>BOOK_ACTIVATION"] --> B["📋 生成计划<br/>STUDY_PLAN"]
        B --> C["📖 Agent 引导学习<br/>LESSON_PROGRESS"]
        C --> D["💬 对话式评估<br/>CHAT_ASSESSMENT"]
        D --> E{"✅ 掌握?"}
        E -->|是| F["🟢 节点变绿<br/>health_score ↑"]
        E -->|否| G["🔴 节点变红<br/>health_score ↓"]
        G --> H["📕 沉淀错题<br/>STUDENT_MISTAKE"]
        H --> I["🎲 变式生成<br/>Variant Engine"]
        I --> J["📅 注入复习任务<br/>PLAN_ITEM"]
        J --> C
        F --> K["🔓 解锁下一课<br/>is_unlocked=true"]
        K --> B
    end

    subgraph AssessTrack["📊 评估双轨"]
        D2["隐式评估<br/>CHAT_ASSESSMENT<br/>对话中自动评估"]
        D3["显式评估<br/>TEST_PAPER + TEST_RECORD<br/>正式测试/自测"]
    end

    subgraph ParentView["👨‍👩‍👧 家长视图"]
        R["📊 AI 柔性周报<br/>PARENT_WEEKLY_REPORT"]
    end

    D --> D2
    D --> D3
    D2 --> E
    D3 --> E
    H -.->|周汇总| R

    style LearnLoop fill:#FFF8E1,stroke:#FFC107,stroke-width:2px
    style AssessTrack fill:#F3E5F5,stroke:#9C27B0
    style ParentView fill:#E8F5E9,stroke:#4CAF50
```

---

## 4. 技术栈选型 (Technology Stack)

```mermaid
graph LR
    subgraph Frontend["🎨 前端"]
        direction TB
        F1["Vue 3 / React"]
        F2["ECharts / D3.js<br/>知识树可视化"]
        F3["PWA + 响应式布局"]
        F4["WebSocket Client<br/>流式对话"]
    end

    subgraph Backend["⚙️ 后端"]
        direction TB
        B1["Python / FastAPI"]
        B2["SQLAlchemy ORM"]
        B3["LangChain / LangGraph<br/>Agent 编排"]
        B4["PageIndex Local<br/>树状 RAG"]
    end

    subgraph Infra["🏗️ 基础设施"]
        direction TB
        I1["PostgreSQL + JSONB"]
        I2["Redis 缓存"]
        I3["阿里云 OSS / S3"]
        I4["Docker + K8s"]
    end

    subgraph AI["🧠 AI 服务"]
        direction TB
        A1["Aliyun qwen-max / 通义千问"]
        A2["多模态 OCR + VLM<br/>(通义/视觉识别提取目录)"]
        A3["PageIndex 树检索引擎"]
        A4["Dual-Tree Mappper<br/>双树语义映射器"]
    end

    Frontend --> Backend --> Infra
    Backend --> AI

    style Frontend fill:#E3F2FD,stroke:#2196F3,stroke-width:2px
    style Backend fill:#FFF3E0,stroke:#FF9800,stroke-width:2px
    style Infra fill:#ECEFF1,stroke:#607D8B,stroke-width:2px
    style AI fill:#F3E5F5,stroke:#9C27B0,stroke-width:2px
```

---

## 5. 数据领域模型总览 (Domain Model Overview)

数据架构按**三大核心领域**组织，覆盖从知识资源到学情追踪的完整生命周期。

```mermaid
graph TB
    subgraph D1["📚 知识与资源领域<br/>Knowledge & Resource Domain"]
        MATERIAL["MATERIAL<br/>教材/讲义"]
        KN["KNOWLEDGE_NODE<br/>知识节点树"]
        QUESTION["QUESTION<br/>题库"]
        LESSON["LESSON<br/>课时单元"]
        MATERIAL --> KN --> QUESTION
        KN --> LESSON
    end

    subgraph D2["👤 用户与书架领域<br/>Identity & Bookshelf Domain"]
        STUDENT["STUDENT<br/>学生"]
        PARENT["PARENT<br/>家长"]
        PB["PARENT_BINDING<br/>亲子绑定"]
        BA["BOOK_ACTIVATION<br/>书架/教材激活"]
        STUDENT --> PB
        PARENT --> PB
        STUDENT --> BA
    end

    subgraph D3["📈 学情与调度领域<br/>Learning State & Scheduling Domain"]
        SNS["STUDENT_NODE_STATE<br/>节点健康度"]
        SP["STUDY_PLAN<br/>学习计划"]
        PI_T["PLAN_ITEM<br/>每日任务"]
        CS["CHAT_SESSION<br/>会话"]
        CM["CHAT_MESSAGE<br/>消息"]
        CA["CHAT_ASSESSMENT<br/>对话评估"]
        LP["LESSON_PROGRESS<br/>课程进度"]
        TP["TEST_PAPER<br/>试卷"]
        TR["TEST_RECORD<br/>答题记录"]
        SM["STUDENT_MISTAKE<br/>错题本"]
        PWR["PARENT_WEEKLY_REPORT<br/>家长周报"]

        SP --> PI_T
        CS --> CM --> CA
        TP --> TR --> SM
        STUDENT --> SNS
        STUDENT --> LP
    end

    BA ---|关联教材| MATERIAL
    SNS ---|追踪节点| KN
    SM ---|挂载节点| KN
    CA ---|评估节点| KN
    LP ---|学习课程| LESSON

    style D1 fill:#E8F5E9,stroke:#4CAF50,stroke-width:2px
    style D2 fill:#E3F2FD,stroke:#2196F3,stroke-width:2px
    style D3 fill:#FFF3E0,stroke:#FF9800,stroke-width:2px
```

---

## 6. 核心场景时序图 (Key Scenario Sequence Diagrams)

### 6.1 场景：Agent 引导式课程学习

```mermaid
sequenceDiagram
    actor S as 👩‍🎓 学生
    participant UI as Student Portal
    participant API as API Gateway
    participant GL as Guided Learning<br/>Controller
    participant TIE as Tree-Index Engine
    participant SQE as Socratic QA Engine
    participant EME as Empathy Engine
    participant DB as PostgreSQL

    S->>UI: 点击课程节点"开始学习"
    UI->>API: POST /lesson/start
    API->>GL: 初始化学习会话
    GL->>TIE: 获取该节点教材内容
    TIE-->>GL: 教材原文 + 关联知识
    GL->>DB: 创建 LESSON_PROGRESS (Step 1)
    
    loop 五步教学法 (导入→讲解→例题→练习→小结)
        GL->>SQE: 生成当前步骤内容
        SQE-->>UI: 流式输出讲解 (SSE)
        UI-->>S: 展示教学内容
        
        SQE->>UI: 抛出理解检查题
        S->>UI: 回答问题
        UI->>API: 提交答案
        API->>SQE: 评估回答
        SQE->>DB: 写入 CHAT_ASSESSMENT
        SQE->>DB: 更新 health_score
        
        alt 学生状态异常(高频错误/深夜)
            SQE->>EME: 触发情绪检测
            EME-->>SQE: 返回安抚策略
        end
        
        GL->>DB: 更新 current_step
    end
    
    GL->>DB: 标记 is_unlocked=true
    GL->>UI: 展示小结卡片 + 解锁通知
```

### 6.2 场景：拍题 → 错题溯源 → 复习闭环

```mermaid
sequenceDiagram
    actor S as 👩‍🎓 学生
    participant UI as Student Portal
    participant API as API Gateway
    participant SQE as Socratic QA Engine
    participant TIE as Tree-Index Engine
    participant VGE as Variant Gen Engine
    participant DRE as Dynamic Routing Engine
    participant DB as PostgreSQL

    S->>UI: 📷 拍照上传错题
    UI->>API: POST /chat/photo
    API->>DB: 存储 MEDIA_ASSET
    
    API->>SQE: OCR识别 + 知识定位
    SQE->>TIE: PageIndex 反向树状推理
    TIE-->>SQE: 推理路径 + root_cause_node_id
    
    SQE-->>UI: "这考的是完全平方公式，教材第28页..."
    
    loop 苏格拉底对话循环
        SQE->>UI: 启发式追问
        S->>UI: 尝试回答
        UI->>SQE: 学生答案
        SQE->>DB: 写入 CHAT_ASSESSMENT
    end
    
    SQE->>DB: 创建 STUDENT_MISTAKE 记录
    SQE->>DB: 节点 health_score ↓ (变黄)
    
    Note over DRE: 次日调度
    DRE->>DB: 扫描 next_review_date 到期的错题
    DRE->>VGE: 请求生成变式题
    VGE-->>DRE: 返回同考点变式
    DRE->>DB: 注入 PLAN_ITEM (REVIEW_VARIANT)
    DRE-->>UI: "学新课前，先看这道老朋友的变形~"
```

---

## 7. 部署架构 (Deployment Architecture)

```mermaid
graph TB
    subgraph CDN["🌍 CDN / 边缘节点"]
        CF["静态资源分发<br/>HTML/CSS/JS/图片"]
    end

    subgraph LB["⚖️ 负载均衡"]
        NX["Nginx / ALB"]
    end

    subgraph AppCluster["🖥️ 应用集群 (Docker/K8s)"]
        direction TB
        subgraph WebPods["Web 服务 Pod"]
            W1["FastAPI 实例 ×N"]
            W2["WebSocket 网关"]
        end
        subgraph WorkerPods["异步任务 Worker"]
            K1["PDF 解析 Worker"]
            K2["报告生成 Worker"]
            K3["计划调度 Worker"]
        end
    end

    subgraph DataLayer["💾 数据层"]
        PG2["PostgreSQL<br/>主从集群"]
        RD["Redis Cluster<br/>会话 & 缓存"]
        MQ["消息队列<br/>(RabbitMQ/Celery)"]
    end

    subgraph ExtServices["☁️ 外部服务"]
        LLM2["LLM API<br/>Aliyun qwen-max"]
        OSS2["对象存储<br/>OSS / S3"]
        EMAIL["邮件服务<br/>SMTP / SES"]
    end

    CF --> NX --> AppCluster
    AppCluster --> DataLayer
    AppCluster --> ExtServices
    WorkerPods --> MQ --> WorkerPods

    style CDN fill:#E3F2FD,stroke:#2196F3
    style LB fill:#ECEFF1,stroke:#607D8B
    style AppCluster fill:#FFF3E0,stroke:#FF9800,stroke-width:2px
    style DataLayer fill:#E8F5E9,stroke:#4CAF50,stroke-width:2px
    style ExtServices fill:#F3E5F5,stroke:#9C27B0
```

---

## 8. 安全与隔离策略 (Security & Isolation)

| 维度 | 策略 | 实现方式 |
|:---|:---|:---|
| **身份认证** | JWT Token + 刷新令牌机制 | FastAPI Security + OAuth2 |
| **角色隔离** | 学生/家长/管理员三级 RBAC | 中间件路由级别拦截 |
| **数据隔离** | 学生数据按 `student_id` 严格隔离 | 数据库行级安全策略 (RLS) |
| **媒体安全** | 用户上传图片防盗链 + 访问签名 | OSS 签名 URL，过期时间 15min |
| **知识边界** | Agent 回答严格限制在教材树内 | PageIndex 树搜索 + Prompt 注入防护 |
| **组卷防超纲** | `is_unlocked` 硬锁校验 | 数据库查询级强制过滤 |
| **快照保护** | 试卷题面物理快照，不受源库变动影响 | `snapshot_question_md` JSONB 静态化 |

---

## 9. 性能与扩展性设计 (Performance & Scalability)

| 关注点 | 设计方案 |
|:---|:---|
| **流式响应** | LLM 输出通过 SSE/WebSocket 实时推送，首字延迟 < 500ms |
| **知识树缓存** | 高频访问的教材知识树缓存至 Redis，TTL 24h |
| **异步解析** | PDF 上传后异步 Worker 处理，不阻塞主线程 |
| **弹性扩缩** | K8s HPA 基于 CPU/内存自动扩缩 Web Pod |
| **数据库优化** | `KNOWLEDGE_NODE` 树结构使用物化路径 + 递归 CTE 优化查询 |
| **LLM 成本控制** | 分级调用策略：简单判断用轻量模型，深度推理用 Aliyun qwen-max |
