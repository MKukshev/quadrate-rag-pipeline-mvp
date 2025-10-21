"""
Configurable Role-Based Access Control (RBAC)
Роли и их права конфигурируются через YAML/JSON файлы или переменные окружения
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import json
import yaml
from pathlib import Path


class EntityType(str, Enum):
    """Тип сущности - человек или бот"""
    HUMAN = "human"
    AGENT = "agent"


@dataclass
class RolePermissions:
    """
    Права доступа для роли
    """
    role_name: str
    entity_type: EntityType  # human или agent
    description: str
    
    # Типы документов, которые может видеть эта роль
    allowed_doc_types: Optional[List[str]] = None  # None = все типы
    
    # Уровни видимости, которые может видеть
    allowed_visibility: List[str] = field(default_factory=lambda: ["public"])
    
    # Максимальный уровень безопасности (0-5)
    max_security_level: int = 0
    
    # Департаменты, к которым есть доступ
    allowed_departments: Optional[List[str]] = None  # None = все департаменты
    
    # Может ли создавать документы
    can_create: bool = False
    
    # Может ли редактировать свои документы
    can_edit_own: bool = False
    
    # Может ли редактировать чужие документы
    can_edit_others: bool = False
    
    # Может ли удалять свои документы
    can_delete_own: bool = False
    
    # Может ли удалять чужие документы
    can_delete_others: bool = False
    
    # Может ли изменять права доступа к документам
    can_manage_access: bool = False
    
    # Дополнительные метаданные
    metadata: Dict = field(default_factory=dict)
    
    def can_access_doc_type(self, doc_type: str) -> bool:
        """Проверка доступа к типу документа"""
        if self.allowed_doc_types is None:
            return True
        return doc_type in self.allowed_doc_types
    
    def can_access_visibility(self, visibility: str) -> bool:
        """Проверка доступа к уровню видимости"""
        return visibility in self.allowed_visibility
    
    def can_access_security_level(self, security_level: int) -> bool:
        """Проверка доступа к уровню безопасности"""
        return security_level <= self.max_security_level
    
    def can_access_department(self, department: Optional[str]) -> bool:
        """Проверка доступа к департаменту"""
        if not department:  # Документы без департамента видны всем
            return True
        if self.allowed_departments is None:  # Роль имеет доступ ко всем департаментам
            return True
        return department in self.allowed_departments


class RoleRegistry:
    """
    Реестр ролей с конфигурацией
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self._roles: Dict[str, RolePermissions] = {}
        self._role_hierarchy: Dict[str, List[str]] = {}  # role -> inherited_roles
        
        if config_path:
            self.load_from_file(config_path)
        else:
            self._load_default_roles()
    
    def _load_default_roles(self):
        """Загрузка базовых ролей по умолчанию"""
        
        # ===== РОЛИ ДЛЯ ЛЮДЕЙ =====
        
        # Guest - минимальные права
        self.register_role(RolePermissions(
            role_name="guest",
            entity_type=EntityType.HUMAN,
            description="Гость с минимальными правами доступа",
            allowed_doc_types=None,  # Видит все типы
            allowed_visibility=["public"],
            max_security_level=0,
            can_create=False,
            can_edit_own=False,
            can_delete_own=False,
        ))
        
        # Developer - разработчик
        self.register_role(RolePermissions(
            role_name="developer",
            entity_type=EntityType.HUMAN,
            description="Разработчик с доступом к техническим документам",
            allowed_doc_types=[
                "technical_docs",
                "work_plans",
                "protocols",
                "unstructured"
            ],
            allowed_visibility=["public", "team", "channel"],
            max_security_level=3,
            allowed_departments=["engineering", "product"],
            can_create=True,
            can_edit_own=True,
            can_delete_own=True,
            can_manage_access=False,
        ))
        
        # Business Analyst - бизнес-аналитик
        self.register_role(RolePermissions(
            role_name="business_analyst",
            entity_type=EntityType.HUMAN,
            description="Бизнес-аналитик с доступом к планам и аналитике",
            allowed_doc_types=[
                "work_plans",
                "presentations",
                "email_correspondence",
                "technical_docs",
                "protocols"
            ],
            allowed_visibility=["public", "team", "channel"],
            max_security_level=3,
            allowed_departments=["product", "business", "engineering"],
            can_create=True,
            can_edit_own=True,
            can_delete_own=True,
            can_manage_access=False,
        ))
        
        # Technical Writer - технический писатель
        self.register_role(RolePermissions(
            role_name="technical_writer",
            entity_type=EntityType.HUMAN,
            description="Технический писатель для создания документации",
            allowed_doc_types=[
                "technical_docs",
                "protocols",
                "presentations",
                "unstructured"
            ],
            allowed_visibility=["public", "team", "channel"],
            max_security_level=2,
            allowed_departments=["documentation", "engineering", "product"],
            can_create=True,
            can_edit_own=True,
            can_edit_others=True,  # Может редактировать документацию других
            can_delete_own=True,
            can_manage_access=False,
        ))
        
        # Project Manager - менеджер проектов
        self.register_role(RolePermissions(
            role_name="project_manager",
            entity_type=EntityType.HUMAN,
            description="Менеджер проектов с широким доступом",
            allowed_doc_types=None,  # Видит все типы
            allowed_visibility=["public", "team", "channel"],
            max_security_level=4,
            allowed_departments=None,  # Доступ ко всем департаментам
            can_create=True,
            can_edit_own=True,
            can_delete_own=True,
            can_manage_access=True,
        ))
        
        # Admin - администратор
        self.register_role(RolePermissions(
            role_name="admin",
            entity_type=EntityType.HUMAN,
            description="Администратор с полными правами",
            allowed_doc_types=None,
            allowed_visibility=["public", "team", "channel", "private"],
            max_security_level=5,
            allowed_departments=None,
            can_create=True,
            can_edit_own=True,
            can_edit_others=True,
            can_delete_own=True,
            can_delete_others=True,
            can_manage_access=True,
        ))
        
        # ===== РОЛИ ДЛЯ БОТОВ/АГЕНТОВ =====
        
        # Research Agent
        self.register_role(RolePermissions(
            role_name="agent_research",
            entity_type=EntityType.AGENT,
            description="Бот для исследований и поиска технической информации",
            allowed_doc_types=[
                "technical_docs",
                "work_plans",
                "presentations",
                "protocols",
                "unstructured"
            ],
            allowed_visibility=["public", "team", "channel"],
            max_security_level=2,
            can_create=False,
            can_edit_own=False,
            can_delete_own=False,
        ))
        
        # Support Agent
        self.register_role(RolePermissions(
            role_name="agent_support",
            entity_type=EntityType.AGENT,
            description="Бот поддержки для ответов на вопросы",
            allowed_doc_types=[
                "protocols",
                "technical_docs",
                "email_correspondence"
            ],
            allowed_visibility=["public", "channel"],
            max_security_level=1,
            can_create=False,
        ))
        
        # Analytics Agent
        self.register_role(RolePermissions(
            role_name="agent_analytics",
            entity_type=EntityType.AGENT,
            description="Бот аналитики с широким доступом для анализа данных",
            allowed_doc_types=None,  # Видит все типы
            allowed_visibility=["public", "team", "channel"],
            max_security_level=3,
            can_create=False,
        ))
        
        # Summarizer Agent
        self.register_role(RolePermissions(
            role_name="agent_summarizer",
            entity_type=EntityType.AGENT,
            description="Бот для суммаризации переписки",
            allowed_doc_types=[
                "email_correspondence",
                "messenger_correspondence"
            ],
            allowed_visibility=["public", "team", "channel"],
            max_security_level=1,
            can_create=False,
        ))
        
        # Admin Agent
        self.register_role(RolePermissions(
            role_name="agent_admin",
            entity_type=EntityType.AGENT,
            description="Административный бот с полным доступом",
            allowed_doc_types=None,
            allowed_visibility=["public", "team", "channel", "private"],
            max_security_level=5,
            can_create=False,
        ))
    
    def register_role(self, role: RolePermissions):
        """Регистрация роли"""
        self._roles[role.role_name] = role
    
    def get_role(self, role_name: str) -> Optional[RolePermissions]:
        """Получить роль по имени"""
        return self._roles.get(role_name)
    
    def list_roles(self, entity_type: Optional[EntityType] = None) -> List[RolePermissions]:
        """Список всех ролей"""
        if entity_type:
            return [r for r in self._roles.values() if r.entity_type == entity_type]
        return list(self._roles.values())
    
    def role_exists(self, role_name: str) -> bool:
        """Проверка существования роли"""
        return role_name in self._roles
    
    def add_role_inheritance(self, role_name: str, inherits_from: List[str]):
        """
        Добавить наследование ролей
        Например: project_manager наследует права от developer
        """
        self._role_hierarchy[role_name] = inherits_from
    
    def get_effective_permissions(self, role_name: str) -> RolePermissions:
        """
        Получить эффективные права с учетом наследования
        """
        role = self.get_role(role_name)
        if not role:
            raise ValueError(f"Role {role_name} not found")
        
        # Если есть наследование, объединяем права
        if role_name in self._role_hierarchy:
            inherited_roles = self._role_hierarchy[role_name]
            for inherited_role_name in inherited_roles:
                inherited_role = self.get_role(inherited_role_name)
                if inherited_role:
                    role = self._merge_permissions(role, inherited_role)
        
        return role
    
    def _merge_permissions(self, role: RolePermissions, inherited: RolePermissions) -> RolePermissions:
        """Объединение прав двух ролей (приоритет у основной роли)"""
        # Объединяем allowed_doc_types
        if role.allowed_doc_types is None or inherited.allowed_doc_types is None:
            merged_doc_types = None
        else:
            merged_doc_types = list(set(role.allowed_doc_types + inherited.allowed_doc_types))
        
        # Объединяем visibility
        merged_visibility = list(set(role.allowed_visibility + inherited.allowed_visibility))
        
        # Берем максимальный security_level
        merged_security = max(role.max_security_level, inherited.max_security_level)
        
        # Объединяем departments
        if role.allowed_departments is None or inherited.allowed_departments is None:
            merged_departments = None
        else:
            merged_departments = list(set(role.allowed_departments + inherited.allowed_departments))
        
        return RolePermissions(
            role_name=role.role_name,
            entity_type=role.entity_type,
            description=role.description,
            allowed_doc_types=merged_doc_types,
            allowed_visibility=merged_visibility,
            max_security_level=merged_security,
            allowed_departments=merged_departments,
            can_create=role.can_create or inherited.can_create,
            can_edit_own=role.can_edit_own or inherited.can_edit_own,
            can_edit_others=role.can_edit_others or inherited.can_edit_others,
            can_delete_own=role.can_delete_own or inherited.can_delete_own,
            can_delete_others=role.can_delete_others or inherited.can_delete_others,
            can_manage_access=role.can_manage_access or inherited.can_manage_access,
            metadata={**inherited.metadata, **role.metadata}
        )
    
    def load_from_file(self, config_path: Path):
        """
        Загрузка ролей из YAML или JSON файла
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix in ['.yaml', '.yml']:
                config = yaml.safe_load(f)
            else:
                config = json.load(f)
        
        # Загрузка ролей
        for role_config in config.get('roles', []):
            entity_type = EntityType(role_config.get('entity_type', 'human'))
            
            role = RolePermissions(
                role_name=role_config['role_name'],
                entity_type=entity_type,
                description=role_config.get('description', ''),
                allowed_doc_types=role_config.get('allowed_doc_types'),
                allowed_visibility=role_config.get('allowed_visibility', ['public']),
                max_security_level=role_config.get('max_security_level', 0),
                allowed_departments=role_config.get('allowed_departments'),
                can_create=role_config.get('can_create', False),
                can_edit_own=role_config.get('can_edit_own', False),
                can_edit_others=role_config.get('can_edit_others', False),
                can_delete_own=role_config.get('can_delete_own', False),
                can_delete_others=role_config.get('can_delete_others', False),
                can_manage_access=role_config.get('can_manage_access', False),
                metadata=role_config.get('metadata', {}),
            )
            self.register_role(role)
        
        # Загрузка иерархии ролей
        for role_name, inherits_from in config.get('role_inheritance', {}).items():
            self.add_role_inheritance(role_name, inherits_from)
    
    def export_to_file(self, output_path: Path):
        """Экспорт конфигурации ролей в файл"""
        config = {
            'roles': [
                {
                    'role_name': role.role_name,
                    'entity_type': role.entity_type.value,
                    'description': role.description,
                    'allowed_doc_types': role.allowed_doc_types,
                    'allowed_visibility': role.allowed_visibility,
                    'max_security_level': role.max_security_level,
                    'allowed_departments': role.allowed_departments,
                    'can_create': role.can_create,
                    'can_edit_own': role.can_edit_own,
                    'can_edit_others': role.can_edit_others,
                    'can_delete_own': role.can_delete_own,
                    'can_delete_others': role.can_delete_others,
                    'can_manage_access': role.can_manage_access,
                    'metadata': role.metadata,
                }
                for role in self._roles.values()
            ],
            'role_inheritance': self._role_hierarchy
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if output_path.suffix in ['.yaml', '.yml']:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            else:
                json.dump(config, f, indent=2, ensure_ascii=False)


# Глобальный реестр ролей (singleton)
_global_registry: Optional[RoleRegistry] = None


def get_role_registry(config_path: Optional[Path] = None) -> RoleRegistry:
    """Получить глобальный реестр ролей"""
    global _global_registry
    if _global_registry is None:
        _global_registry = RoleRegistry(config_path)
    return _global_registry


def reload_roles(config_path: Optional[Path] = None):
    """Перезагрузить конфигурацию ролей"""
    global _global_registry
    _global_registry = RoleRegistry(config_path)

