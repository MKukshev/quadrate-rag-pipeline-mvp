# Диаграммы архитектуры контроля доступа

## 🏗️ Общая архитектура системы с ACL

```mermaid
graph TB
    subgraph "Client Layer"
        User[👤 User]
        Bot[🤖 Agent Bot]
    end
    
    subgraph "API Layer"
        Auth[🔐 Authentication<br/>JWT Validation]
        API[FastAPI Backend]
        ACL[AccessControlService]
    end
    
    subgraph "Storage Layer"
        Qdrant[(Qdrant<br/>Vector DB)]
        Whoosh[(Whoosh<br/>BM25 Index)]
        Redis[(Redis<br/>Cache)]
    end
    
    subgraph "External Services"
        LLM[Ollama LLM]
        Embedder[Sentence<br/>Transformers]
    end
    
    User -->|JWT Token| Auth
    Bot -->|JWT Token| Auth
    Auth -->|Validated Context| API
    API --> ACL
    ACL -->|Filtered Query| Qdrant
    API --> Whoosh
    API --> Redis
    API --> LLM
    API --> Embedder
    
    style ACL fill:#ff9,stroke:#333,stroke-width:4px
    style Auth fill:#9ff,stroke:#333,stroke-width:2px
```

## 🔄 Поток запроса с контролем доступа

```mermaid
sequenceDiagram
    participant User as 👤 User/Bot
    participant API as FastAPI
    participant Auth as Auth Service
    participant ACL as ACL Service
    participant Qdrant as Qdrant DB
    participant Filter as Post-Filter
    
    User->>API: POST /search?q="architecture"
    API->>Auth: Validate JWT Token
    Auth-->>API: User Context (user_id, space_id, role)
    
    API->>ACL: build_access_filter(context, doc_types)
    ACL-->>API: Qdrant Filter Object
    
    Note over ACL: Filter includes:<br/>- space_id<br/>- channel_id<br/>- visibility<br/>- agent_roles<br/>- security_level
    
    API->>Qdrant: search(query_vector, filter, top_k)
    Qdrant-->>API: Filtered Results (pre-filtered by HNSW+filters)
    
    API->>Filter: Double-check access (defense in depth)
    Filter->>ACL: can_access_document(context, payload)
    ACL-->>Filter: True/False for each result
    Filter-->>API: Final Filtered Results
    
    API-->>User: Search Results
```

## 🗄️ Структура данных в Qdrant

```mermaid
erDiagram
    POINT {
        uuid id PK
        vector vector
        json payload
    }
    
    PAYLOAD {
        string doc_id
        string space_id "Indexed"
        string channel_id "Indexed"
        string doc_type "Indexed"
        int chunk_index
        text text
        string visibility "Indexed: private|team|channel|public"
        string owner_id "Indexed"
        list access_list "User IDs with explicit access"
        list agent_roles "Agent roles allowed: research,support,etc"
        int security_level "Indexed: 0-5"
        string department "Indexed"
        string project_id
        timestamp created_at
        timestamp expires_at
    }
    
    POINT ||--|| PAYLOAD : contains
```

## 🎭 Матрица контроля доступа

```mermaid
graph LR
    subgraph "Access Control Layers"
        L1[Layer 1:<br/>Space Isolation]
        L2[Layer 2:<br/>Channel Isolation]
        L3[Layer 3:<br/>Visibility Level]
        L4[Layer 4:<br/>Role/Agent Check]
        L5[Layer 5:<br/>Security Clearance]
    end
    
    Request[Incoming Request] --> L1
    L1 -->|space_id match| L2
    L2 -->|channel_id match or null| L3
    L3 -->|visibility rules| L4
    L4 -->|role/agent_role check| L5
    L5 -->|security_level <=| Allow[✅ Access Granted]
    
    L1 -->|mismatch| Deny[❌ Access Denied]
    L2 -->|mismatch| Deny
    L3 -->|no permission| Deny
    L4 -->|role not allowed| Deny
    L5 -->|clearance too low| Deny
    
    style Allow fill:#9f9
    style Deny fill:#f99
```

## 🤖 Роли агентов и их доступ

```mermaid
graph TD
    subgraph "Agent Roles"
        Research[🔬 Research Agent]
        Support[💬 Support Agent]
        Analytics[📊 Analytics Agent]
        Summarizer[📝 Summarizer Agent]
        Admin[👑 Admin Agent]
    end
    
    subgraph "Document Types"
        TD[technical_docs]
        WP[work_plans]
        PR[presentations]
        PRT[protocols]
        EC[email_correspondence]
        MC[messenger_correspondence]
        UN[unstructured]
    end
    
    Research --> TD
    Research --> WP
    Research --> PR
    Research --> PRT
    Research --> UN
    
    Support --> PRT
    Support --> TD
    Support --> EC
    
    Analytics --> TD
    Analytics --> WP
    Analytics --> PR
    Analytics --> PRT
    Analytics --> EC
    Analytics --> MC
    Analytics --> UN
    
    Summarizer --> EC
    Summarizer --> MC
    
    Admin --> TD
    Admin --> WP
    Admin --> PR
    Admin --> PRT
    Admin --> EC
    Admin --> MC
    Admin --> UN
    
    style Research fill:#ff9
    style Support fill:#9f9
    style Analytics fill:#99f
    style Summarizer fill:#f9f
    style Admin fill:#f99
```

## 📊 Уровни видимости документов

```mermaid
graph TB
    subgraph "Visibility Hierarchy"
        Private[🔒 Private<br/>Only Owner & Admin]
        Team[👥 Team<br/>All Members in Space]
        Channel[💬 Channel<br/>Channel Participants]
        Public[🌐 Public<br/>Everyone in Space]
    end
    
    Private -->|Owner shares| Team
    Team -->|Restrict to| Channel
    Channel -->|Promote to| Public
    
    Private -.->|Admin always has access| AdminAccess[👑 Admin Override]
    
    style Private fill:#f99,stroke:#333,stroke-width:3px
    style Team fill:#ff9,stroke:#333,stroke-width:2px
    style Channel fill:#9f9,stroke:#333,stroke-width:2px
    style Public fill:#9ff,stroke:#333,stroke-width:1px
    style AdminAccess fill:#f9f,stroke:#333,stroke-width:4px
```

## 🔍 Процесс индексации с ACL

```mermaid
flowchart TD
    Start([User uploads document]) --> Auth{Authenticated?}
    Auth -->|No| Reject[❌ 401 Unauthorized]
    Auth -->|Yes| ValidSpace{Valid Space?}
    
    ValidSpace -->|No| Reject2[❌ 403 Forbidden]
    ValidSpace -->|Yes| Parse[Parse Document]
    
    Parse --> Chunk[Split into Chunks]
    Chunk --> Clean[Clean & Deduplicate]
    
    Clean --> BuildACL[Build ACL Metadata]
    BuildACL --> ACLFields{ACL Fields}
    
    ACLFields --> |owner_id| Owner[Set Owner ID]
    ACLFields --> |visibility| Vis[Set Visibility]
    ACLFields --> |agent_roles| Agents[Set Agent Roles]
    ACLFields --> |security_level| Security[Set Security Level]
    
    Owner --> Augment[Augment Payload]
    Vis --> Augment
    Agents --> Augment
    Security --> Augment
    
    Augment --> Embed[Generate Embeddings]
    Embed --> Upsert[Upsert to Qdrant]
    Upsert --> Index[Index in Whoosh]
    Index --> Success[✅ Document Indexed]
    
    style BuildACL fill:#ff9,stroke:#333,stroke-width:3px
    style Success fill:#9f9,stroke:#333,stroke-width:2px
```

## 🔐 Сценарий: Пользователь делится документом

```mermaid
sequenceDiagram
    participant Alice as 👤 Alice (Owner)
    participant API as API Server
    participant ACL as ACL Service
    participant Qdrant as Qdrant DB
    participant Bob as 👤 Bob (Team Member)
    participant Bot as 🤖 Research Bot
    
    Note over Alice,Qdrant: Initial State: Private Document
    
    Alice->>API: POST /document-access<br/>visibility="team"<br/>agent_roles=["research"]
    API->>ACL: Check ownership
    ACL-->>API: Alice is owner ✓
    
    API->>Qdrant: Update all chunks<br/>payload.visibility = "team"<br/>payload.agent_roles = ["research"]
    Qdrant-->>API: Updated
    API-->>Alice: ✅ Access Updated
    
    Note over Alice,Bot: Now accessible by team & research bot
    
    Bob->>API: GET /search?q="report"
    API->>ACL: build_access_filter(Bob, team_1)
    ACL-->>API: Filter with team visibility
    API->>Qdrant: search(filter)
    Qdrant-->>API: Results include Alice's document
    API-->>Bob: ✅ Document visible
    
    Bot->>API: GET /search?q="report"<br/>agent_role="research"
    API->>ACL: build_access_filter(Bot, research)
    ACL-->>API: Filter with research role
    API->>Qdrant: search(filter)
    Qdrant-->>API: Results include Alice's document
    API-->>Bot: ✅ Document visible
```

## 🏢 Multi-Tenant Architecture (Hybrid Approach)

```mermaid
graph TB
    subgraph "Physical Isolation by Space"
        Collection1[(docs_company_acme)]
        Collection2[(docs_company_beta)]
        Collection3[(docs_company_gamma)]
    end
    
    subgraph "Company ACME"
        subgraph "Logical Isolation - Channels"
            Ch1[#engineering]
            Ch2[#sales]
            Ch3[#leadership]
        end
        
        subgraph "Logical Isolation - Visibility"
            V1[Private Docs]
            V2[Team Docs]
            V3[Public Docs]
        end
        
        subgraph "Logical Isolation - Roles"
            U1[👤 Users]
            B1[🤖 Bots]
        end
    end
    
    Collection1 --> Ch1
    Collection1 --> Ch2
    Collection1 --> Ch3
    
    Ch1 --> V1
    Ch1 --> V2
    Ch1 --> V3
    
    V1 --> U1
    V2 --> U1
    V2 --> B1
    V3 --> U1
    V3 --> B1
    
    style Collection1 fill:#9ff,stroke:#333,stroke-width:4px
    style Ch1 fill:#ff9,stroke:#333,stroke-width:2px
    style V1 fill:#f99,stroke:#333,stroke-width:2px
```

## ⚡ Performance: Indexed vs Non-Indexed Filtering

```mermaid
graph LR
    subgraph "With Payload Indexes"
        Q1[Query] -->|1. HNSW Search| V1[Vector Results<br/>1000 candidates]
        V1 -->|2. Indexed Filter<br/>space_id, visibility| F1[Filtered Results<br/>50 matches]
        F1 -->|5-20ms overhead| R1[Final Results]
    end
    
    subgraph "Without Indexes"
        Q2[Query] -->|1. HNSW Search| V2[Vector Results<br/>1000 candidates]
        V2 -->|2. Full Scan Filter<br/>space_id, visibility| F2[Filtered Results<br/>50 matches]
        F2 -->|100-500ms overhead| R2[Final Results]
    end
    
    style F1 fill:#9f9
    style F2 fill:#f99
```

## 🔄 State Transitions: Document Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Draft: User creates private doc
    
    Draft --> TeamReview: share_with_team()
    TeamReview --> ChannelDiscussion: move_to_channel()
    ChannelDiscussion --> Published: make_public()
    
    Draft --> Published: publish_directly()
    TeamReview --> Published: approve_and_publish()
    
    Published --> Archived: archive()
    Archived --> [*]: delete()
    
    Draft --> [*]: delete()
    
    note right of Draft
        visibility: private
        owner_id: user_alice
        agent_roles: []
    end note
    
    note right of TeamReview
        visibility: team
        access_list: [bob, charlie]
        agent_roles: [research]
    end note
    
    note right of Published
        visibility: public
        agent_roles: [research, support, analytics]
    end note
```

## 🎯 Decision Tree: Can User/Agent Access Document?

```mermaid
graph TD
    Start{Incoming Request} -->|Extract| Context[Access Context:<br/>user_id/agent_id<br/>space_id<br/>role]
    
    Context --> CheckSpace{space_id<br/>matches?}
    CheckSpace -->|No| Deny1[❌ Deny]
    CheckSpace -->|Yes| CheckChannel{channel_id<br/>required & matches?}
    
    CheckChannel -->|No| Deny2[❌ Deny]
    CheckChannel -->|Yes or N/A| CheckVis{Check Visibility}
    
    CheckVis -->|private| CheckOwner{Is Owner or Admin?}
    CheckOwner -->|No| Deny3[❌ Deny]
    CheckOwner -->|Yes| Allow1[✅ Allow]
    
    CheckVis -->|team| CheckTeam{In Team?}
    CheckTeam -->|No| Deny4[❌ Deny]
    CheckTeam -->|Yes| CheckAgent1{Is Agent?}
    
    CheckVis -->|channel| CheckAgent2{Is Agent?}
    CheckVis -->|public| CheckAgent3{Is Agent?}
    
    CheckAgent1 -->|No| Allow2[✅ Allow User]
    CheckAgent1 -->|Yes| CheckRole1{Role in<br/>agent_roles?}
    CheckRole1 -->|No| Deny5[❌ Deny]
    CheckRole1 -->|Yes| CheckDocType1{Doc type<br/>allowed?}
    CheckDocType1 -->|No| Deny6[❌ Deny]
    CheckDocType1 -->|Yes| Allow3[✅ Allow Bot]
    
    CheckAgent2 -->|No| Allow4[✅ Allow User]
    CheckAgent2 -->|Yes| CheckRole2{Role in<br/>agent_roles?}
    CheckRole2 -->|Yes| CheckDocType2{Doc type<br/>allowed?}
    CheckRole2 -->|No| Deny7[❌ Deny]
    CheckDocType2 -->|Yes| Allow5[✅ Allow Bot]
    CheckDocType2 -->|No| Deny8[❌ Deny]
    
    CheckAgent3 -->|No| Allow6[✅ Allow User]
    CheckAgent3 -->|Yes| CheckRole3{Role in<br/>agent_roles?}
    CheckRole3 -->|Yes| Allow7[✅ Allow Bot]
    CheckRole3 -->|No| Deny9[❌ Deny]
    
    style Allow1 fill:#9f9
    style Allow2 fill:#9f9
    style Allow3 fill:#9f9
    style Allow4 fill:#9f9
    style Allow5 fill:#9f9
    style Allow6 fill:#9f9
    style Allow7 fill:#9f9
    style Deny1 fill:#f99
    style Deny2 fill:#f99
    style Deny3 fill:#f99
    style Deny4 fill:#f99
    style Deny5 fill:#f99
    style Deny6 fill:#f99
    style Deny7 fill:#f99
    style Deny8 fill:#f99
    style Deny9 fill:#f99
```

## 📈 Scalability: Growth Scenarios

```mermaid
graph TD
    subgraph "Small (< 100K docs)"
        S1[Single Collection<br/>+ Payload Filters]
        S1 --> S1P[✓ Simple<br/>✓ Fast<br/>✓ Low overhead]
    end
    
    subgraph "Medium (100K - 1M docs)"
        M1[Hybrid Approach<br/>Collection per Space<br/>+ Payload Filters]
        M1 --> M1P[✓ Tenant isolation<br/>✓ Scalable<br/>✓ Balanced performance]
    end
    
    subgraph "Large (1M+ docs)"
        L1[Sharded Collections<br/>+ External ACL Service<br/>+ Redis Cache]
        L1 --> L1P[✓ Horizontal scaling<br/>✓ Dynamic ACL<br/>✓ High throughput]
    end
    
    S1 -->|Growth| M1
    M1 -->|Growth| L1
    
    style M1 fill:#9f9,stroke:#333,stroke-width:3px
```

---

## 🛠️ Диаграммы для разработчиков

### Класс-диаграмма: ACL Service

```mermaid
classDiagram
    class AccessContext {
        +str user_id
        +str agent_id
        +AgentRole agent_role
        +UserRole user_role
        +str space_id
        +str channel_id
        +List~str~ team_ids
        +int security_clearance
        +bool is_agent
        +bool is_human
    }
    
    class AgentRole {
        <<enumeration>>
        RESEARCH
        SUPPORT
        ANALYTICS
        SUMMARIZER
        ADMIN
    }
    
    class Visibility {
        <<enumeration>>
        PRIVATE
        TEAM
        CHANNEL
        PUBLIC
    }
    
    class AccessControlService {
        +AGENT_DOC_TYPE_ACCESS: Dict
        +build_access_filter(context, doc_types): Filter
        +can_access_document(context, payload): bool
        +get_user_spaces(user_id): List~str~
        +get_user_channels(user_id, space_id): List~str~
    }
    
    class QdrantStoreACL {
        +ensure_collection()
        +upsert_chunks_with_acl(...)
        +semantic_search_with_acl(...)
        +delete_by_doc(doc_id, context)
        +update_document_access(...)
    }
    
    AccessContext --> AgentRole
    AccessContext --> Visibility
    AccessControlService --> AccessContext
    QdrantStoreACL --> AccessControlService
```

---

## 📝 Легенда символов

- 👤 **User** - Человек-пользователь
- 🤖 **Bot/Agent** - Бот-агент с определенной ролью
- 🔐 **Auth** - Аутентификация и авторизация
- 🔒 **Private** - Приватный документ
- 👥 **Team** - Командный доступ
- 💬 **Channel** - Доступ на уровне канала
- 🌐 **Public** - Публичный доступ
- ✅ **Allow** - Доступ разрешен
- ❌ **Deny** - Доступ запрещен
- 👑 **Admin** - Администратор с полным доступом

