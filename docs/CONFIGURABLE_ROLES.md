# Конфигурируемая система ролей

## 🎯 Обзор

Система ролей полностью конфигурируется через YAML/JSON файлы. Вы можете определить произвольные роли для людей и ботов без изменения кода.

## 📁 Файлы

- **`backend/services/roles_config.py`** - Система управления ролями
- **`config/roles.yaml`** - Конфигурация ролей (редактируйте этот файл)
- **`backend/services/access_control.py`** - Обновлен для использования конфигурируемых ролей

## 🚀 Использование

### 1. Определение новой роли в `config/roles.yaml`

```yaml
roles:
  - role_name: data_scientist
    entity_type: human
    description: "Data Scientist с доступом ко всем данным"
    allowed_doc_types: null  # null = все типы документов
    allowed_visibility:
      - public
      - team
      - channel
    max_security_level: 4
    allowed_departments:
      - data
      - analytics
      - engineering
    can_create: true
    can_edit_own: true
    can_edit_others: false
    can_delete_own: true
    can_delete_others: false
    can_manage_access: false
    metadata:
      color: "#009688"
      icon: "🔬"
```

### 2. Создание контекста с новой ролью

```python
from backend.services.access_control import create_context_for_user

# Для людей
context = create_context_for_user(
    user_id="user_alice",
    role_name="data_scientist",  # Имя из конфигурации
    space_id="company_acme",
    department="data"
)

# Для ботов
context = create_context_for_agent(
    agent_id="bot_research_01",
    role_name="agent_research",  # Имя из конфигурации
    space_id="company_acme"
)
```

### 3. Использование в API

```python
# В app.py
@app.get("/search")
def search(
    q: str,
    role_name: str,  # "developer", "business_analyst", "agent_research", etc.
    current_user: Dict = Depends(get_current_user)
):
    # Создать контекст с ролью из конфигурации
    context = create_context_for_user(
        user_id=current_user["user_id"],
        role_name=role_name,
        space_id=current_user["space_id"]
    )
    
    # Поиск с ACL
    results = semantic_search_with_acl(q, context, top_k=5)
    return results
```

## 📋 Поля роли

### Обязательные поля

| Поле | Тип | Описание |
|------|-----|----------|
| `role_name` | string | Уникальное имя роли (например, "developer", "business_analyst") |
| `entity_type` | string | Тип сущности: "human" или "agent" |
| `description` | string | Описание роли |

### Права доступа

| Поле | Тип | Описание |
|------|-----|----------|
| `allowed_doc_types` | list или null | Типы документов, которые видит роль. null = все типы |
| `allowed_visibility` | list | Уровни видимости: "public", "team", "channel", "private" |
| `max_security_level` | integer | Максимальный уровень безопасности документов (0-5) |
| `allowed_departments` | list или null | Департаменты с доступом. null = все департаменты |

### Операции

| Поле | Тип | Описание |
|------|-----|----------|
| `can_create` | boolean | Может создавать документы |
| `can_edit_own` | boolean | Может редактировать свои документы |
| `can_edit_others` | boolean | Может редактировать чужие документы |
| `can_delete_own` | boolean | Может удалять свои документы |
| `can_delete_others` | boolean | Может удалять чужие документы |
| `can_manage_access` | boolean | Может изменять права доступа к документам |

### Дополнительные

| Поле | Тип | Описание |
|------|-----|----------|
| `metadata` | dict | Произвольные метаданные (цвет, иконка, лимиты запросов) |

## 🏗️ Типы документов (по умолчанию)

- `technical_docs` - Техническая документация
- `work_plans` - Рабочие планы
- `presentations` - Презентации
- `protocols` - Протоколы, инструкции
- `email_correspondence` - Email переписка
- `messenger_correspondence` - Переписка в мессенджерах
- `unstructured` - Неструктурированные документы

## 👥 Примеры ролей для людей

### Developer (Разработчик)
```yaml
- role_name: developer
  entity_type: human
  allowed_doc_types:
    - technical_docs
    - work_plans
    - protocols
  allowed_visibility: [public, team, channel]
  max_security_level: 3
  allowed_departments: [engineering, product]
  can_create: true
  can_edit_own: true
```

### Business Analyst (Бизнес-аналитик)
```yaml
- role_name: business_analyst
  entity_type: human
  allowed_doc_types:
    - work_plans
    - presentations
    - email_correspondence
    - technical_docs
  allowed_visibility: [public, team, channel]
  max_security_level: 3
  allowed_departments: [product, business, engineering, analytics]
  can_create: true
  can_edit_own: true
```

### Technical Writer (Технический писатель)
```yaml
- role_name: technical_writer
  entity_type: human
  allowed_doc_types:
    - technical_docs
    - protocols
    - presentations
  allowed_visibility: [public, team, channel]
  max_security_level: 2
  can_create: true
  can_edit_own: true
  can_edit_others: true  # Может редактировать документацию других
```

### Project Manager (Менеджер проектов)
```yaml
- role_name: project_manager
  entity_type: human
  allowed_doc_types: null  # Видит все типы
  allowed_visibility: [public, team, channel]
  max_security_level: 4
  allowed_departments: null  # Доступ ко всем департаментам
  can_manage_access: true  # Может изменять права доступа
```

## 🤖 Примеры ролей для ботов

### Research Agent (Исследовательский бот)
```yaml
- role_name: agent_research
  entity_type: agent
  allowed_doc_types:
    - technical_docs
    - work_plans
    - presentations
    - protocols
  allowed_visibility: [public, team, channel]
  max_security_level: 2
  metadata:
    max_requests_per_minute: 60
```

### Support Agent (Бот поддержки)
```yaml
- role_name: agent_support
  entity_type: agent
  allowed_doc_types:
    - protocols
    - technical_docs
    - email_correspondence
  allowed_visibility: [public, channel]
  max_security_level: 1
  metadata:
    max_requests_per_minute: 120
    response_timeout: 30
```

### Code Review Agent (Бот для код-ревью)
```yaml
- role_name: agent_code_review
  entity_type: agent
  allowed_doc_types:
    - technical_docs
    - unstructured
  allowed_visibility: [public, team, channel]
  max_security_level: 2
  allowed_departments: [engineering]
  metadata:
    specialized: true
```

## 🔄 Иерархия ролей (наследование)

Роли могут наследовать права от других ролей:

```yaml
role_inheritance:
  senior_developer:
    - developer  # Наследует права developer + свои
  project_manager:
    - business_analyst
  admin:
    - project_manager
    - senior_developer
```

Это позволяет:
- Избежать дублирования конфигурации
- Создавать иерархию ролей
- Автоматически расширять права при повышении

## 🔧 Управление ролями программно

### Загрузка конфигурации

```python
from backend.services.roles_config import get_role_registry, reload_roles
from pathlib import Path

# Загрузка из файла
config_path = Path("config/roles.yaml")
reload_roles(config_path)

# Получить реестр ролей
registry = get_role_registry()
```

### Получение роли

```python
# Получить роль
role = registry.get_role("developer")
print(role.description)
print(role.allowed_doc_types)
print(role.max_security_level)

# Проверить права
can_access_tech_docs = role.can_access_doc_type("technical_docs")
can_access_level_3 = role.can_access_security_level(3)
```

### Список ролей

```python
# Все роли
all_roles = registry.list_roles()

# Только человеческие роли
from backend.services.roles_config import EntityType
human_roles = registry.list_roles(entity_type=EntityType.HUMAN)

# Только роли ботов
agent_roles = registry.list_roles(entity_type=EntityType.AGENT)
```

### Динамическое создание роли

```python
from backend.services.roles_config import RolePermissions, EntityType

# Создать новую роль программно
new_role = RolePermissions(
    role_name="custom_analyst",
    entity_type=EntityType.HUMAN,
    description="Кастомная роль аналитика",
    allowed_doc_types=["work_plans", "presentations"],
    allowed_visibility=["public", "team"],
    max_security_level=2,
    can_create=True,
    can_edit_own=True
)

# Зарегистрировать роль
registry.register_role(new_role)
```

### Экспорт конфигурации

```python
# Экспорт текущей конфигурации в файл
registry.export_to_file(Path("config/roles_backup.yaml"))
```

## 🔍 Примеры использования

### Пример 1: Developer ищет техническую документацию

```python
context = create_context_for_user(
    user_id="user_bob",
    role_name="developer",
    space_id="company_acme",
    department="engineering"
)

results = semantic_search_with_acl(
    q="API documentation",
    access_context=context,
    top_k=5
)

# Developer видит: technical_docs, work_plans, protocols
# Developer НЕ видит: email_correspondence, private documents
```

### Пример 2: Business Analyst анализирует проекты

```python
context = create_context_for_user(
    user_id="user_alice",
    role_name="business_analyst",
    space_id="company_acme",
    department="product"
)

results = semantic_search_with_acl(
    q="quarterly project plans",
    access_context=context,
    doc_types=["work_plans"],
    top_k=10
)

# Business Analyst видит: work_plans, presentations, email (с планами)
```

### Пример 3: Research бот помогает команде

```python
context = create_context_for_agent(
    agent_id="bot_research_01",
    role_name="agent_research",
    space_id="company_acme",
    channel_id="channel_engineering"
)

results = semantic_search_with_acl(
    q="microservices architecture best practices",
    access_context=context,
    top_k=5
)

# Research бот видит: technical_docs, work_plans, presentations, protocols
# Research бот НЕ видит: email, messenger_correspondence
```

### Пример 4: Support бот отвечает клиентам

```python
context = create_context_for_agent(
    agent_id="bot_support_01",
    role_name="agent_support",
    space_id="company_acme",
    channel_id="channel_support"
)

results = semantic_search_with_acl(
    q="how to reset password",
    access_context=context,
    doc_types=["protocols"],
    top_k=3
)

# Support бот видит: protocols, FAQs
# Support бот НЕ видит: work_plans, internal technical docs
```

## 📊 Проверка прав доступа

### Проверка операций

```python
from backend.services.roles_config import get_role_registry

registry = get_role_registry()
role = registry.get_role("developer")

# Может ли создавать документы?
if role.can_create:
    # Allow document creation
    pass

# Может ли редактировать чужие документы?
if role.can_edit_others:
    # Allow editing
    pass

# Может ли изменять права доступа?
if role.can_manage_access:
    # Show access management UI
    pass
```

### Проверка доступа к документу

```python
acl_service = AccessControlService()

document_payload = {
    "doc_type": "technical_docs",
    "visibility": "team",
    "security_level": 2,
    "department": "engineering",
    "owner_id": "user_alice",
    "agent_roles": ["agent_research", "agent_analytics"]
}

# Может ли developer получить доступ?
dev_context = create_context_for_user(
    user_id="user_bob",
    role_name="developer",
    space_id="company_acme"
)

can_access = acl_service.can_access_document(dev_context, document_payload)
print(f"Developer can access: {can_access}")  # True

# Может ли support бот получить доступ?
support_context = create_context_for_agent(
    agent_id="bot_support_01",
    role_name="agent_support",
    space_id="company_acme"
)

can_access = acl_service.can_access_document(support_context, document_payload)
print(f"Support bot can access: {can_access}")  # False (нет в agent_roles)
```

## 🔄 Горячая перезагрузка конфигурации

### Создать endpoint для перезагрузки ролей

```python
@app.post("/admin/reload-roles")
def reload_roles_endpoint(current_user: Dict = Depends(get_current_user)):
    # Проверка прав администратора
    if current_user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    
    # Перезагрузка конфигурации
    from backend.services.roles_config import reload_roles
    reload_roles(Path("config/roles.yaml"))
    
    return {"status": "ok", "message": "Roles configuration reloaded"}
```

Теперь вы можете изменить `config/roles.yaml` и перезагрузить конфигурацию без перезапуска сервиса!

## 🎨 Metadata и расширенные возможности

### Использование metadata для UI

```yaml
roles:
  - role_name: developer
    metadata:
      color: "#3498db"  # Цвет для UI
      icon: "💻"       # Иконка для отображения
      badge: "DEV"     # Бейдж
```

### Использование metadata для rate limiting

```yaml
roles:
  - role_name: agent_support
    entity_type: agent
    metadata:
      max_requests_per_minute: 120
      max_requests_per_hour: 5000
      priority: "high"
```

```python
# В middleware
role = context.role
if role and role.entity_type == EntityType.AGENT:
    rate_limit = role.metadata.get("max_requests_per_minute", 60)
    # Применить rate limiting
```

## 🚦 Best Practices

1. **Принцип наименьших привилегий**: Давайте только необходимые права
2. **Используйте иерархию**: Избегайте дублирования через наследование
3. **Именование ролей**: 
   - Люди: `developer`, `business_analyst`, `admin`
   - Боты: `agent_research`, `agent_support`, `agent_admin`
4. **Документируйте роли**: Добавляйте подробные `description`
5. **Версионируйте**: Храните `config/roles.yaml` в Git
6. **Тестируйте изменения**: Проверяйте права перед деплоем

## 📝 Чеклист добавления новой роли

- [ ] Определить назначение роли
- [ ] Выбрать `entity_type` (human/agent)
- [ ] Определить `allowed_doc_types`
- [ ] Установить `allowed_visibility`
- [ ] Установить `max_security_level`
- [ ] Определить `allowed_departments`
- [ ] Установить операционные права (can_create, can_edit, etc.)
- [ ] Добавить `description`
- [ ] (Опционально) Добавить `metadata`
- [ ] Добавить в `config/roles.yaml`
- [ ] Перезагрузить конфигурацию или перезапустить сервис
- [ ] Протестировать доступ с новой ролью

---

## 🎉 Готово!

Теперь у вас есть полностью конфигурируемая система ролей, которая позволяет:

✅ Определять произвольные роли через YAML  
✅ Разделять роли для людей и ботов  
✅ Гибко настраивать права доступа  
✅ Использовать иерархию ролей  
✅ Изменять конфигурацию без изменения кода  
✅ Горячую перезагрузку конфигурации

