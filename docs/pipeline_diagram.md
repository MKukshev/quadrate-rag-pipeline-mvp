# Pipeline обработки пользовательского запроса

```mermaid
flowchart TD
    A[Клиентский запрос<br/>/search или /ask] --> B[FastAPI endpoint]
    B --> C[Определение doc_types<br/>ручной ввод или авто по ключевым словам]
    C --> D[Адаптивный выбор top_k<br/>TOP_K_MIN..TOP_K_MAX]
    D --> E{Попадание в кэш?}
    E -- да --> F1[Извлечь ответ из кэша<br>обновить метрики]
    F1 --> Z[Ответ клиенту]
    E -- нет --> G[Гибридный поиск]

    subgraph Hybrid_Search
        G --> G1[Qdrant HNSW поиск<br/>m / ef_construct / ef_search]
        G --> G2[Whoosh BM25]
        G1 & G2 --> H[RRF объединение<br/>pool_top_k]
        H --> I{Rerank включён?}
        I -- да --> J[Cross-encoder rerank<br/>max_candidates, batch_size]
        I -- нет --> J1[Пропустить rerank]
        J --> K[MMR lambda & multiplier]
        J1 --> K
        K --> L[1 чанк на документ<br/>+ адаптивная догрузка]
        L --> M[Подсчёт токенов контекста]
    end

    M --> N{Эндпоинт?}
    N -- да --> O[Сформировать ответ<br/>обновить метрики и кэш]
    O --> Z
    N -- нет, /ask --> P[Контекст-компрессия<br/>compress_text, snippet_max_chars]
    P --> Q[Формирование промпта]
    Q --> R[Вызов LLM Ollama<br/>stream / num_predict / timeout]
    R --> S[Сбор ответа и источников]
    S --> T[Сохранить в кэш<br/>обновить метрики]
    T --> Z

    classDef cache fill:#f9f1c1,stroke:#b29d30,color:#050505;
    classDef stage fill:#d5e8f7,stroke:#376996,color:#0b2c4d;
    classDef llm fill:#f6d8d6,stroke:#b14540,color:#520b07;

    class E,F1,O,T cache;
    class B,C,D,G,K,L,M,N,O,P,Q,R,S stage;
    class R llm;
```

- **Очистка данных при индексации** (CLI/API ingestion): `split_markdown` → `clean_chunk` (удаление boilerplate, дублей) → Qdrant/Whoosh.
- **Метрики**: записываются для `/search` и `/ask`, доступны через `GET /metrics` и в блоке `/health`.
- **Кэш**: TTL LRU для обоих эндпоинтов; хранит ответ и предрасчитанные токены.
