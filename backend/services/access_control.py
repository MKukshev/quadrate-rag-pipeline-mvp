"""
Access Control Service for Multi-tenant RAG System
Provides role-based and attribute-based access control for Qdrant
Uses configurable roles from roles_config.py
"""

from typing import List, Optional, Dict, Set
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from .roles_config import (
    get_role_registry,
    RoleRegistry,
    RolePermissions,
    EntityType,
)


class Visibility(str, Enum):
    """Document visibility levels"""
    PRIVATE = "private"      # Only owner
    TEAM = "team"           # Team members
    CHANNEL = "channel"     # Channel participants
    PUBLIC = "public"       # Everyone in space


@dataclass
class AccessContext:
    """Context for access control decisions"""
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    role_name: Optional[str] = None  # NEW: имя роли из конфигурации
    space_id: Optional[str] = None
    channel_id: Optional[str] = None
    team_ids: List[str] = None
    department: Optional[str] = None
    security_clearance: int = 0  # 0-5
    
    # Cached role permissions
    _role_permissions: Optional[RolePermissions] = None
    
    def __post_init__(self):
        if self.team_ids is None:
            self.team_ids = []
    
    @property
    def is_agent(self) -> bool:
        return self.agent_id is not None
    
    @property
    def is_human(self) -> bool:
        return self.user_id is not None
    
    @property
    def role(self) -> Optional[RolePermissions]:
        """Get role permissions from registry"""
        if self._role_permissions is None and self.role_name:
            registry = get_role_registry()
            self._role_permissions = registry.get_effective_permissions(self.role_name)
        return self._role_permissions
    
    @property
    def entity_type(self) -> Optional[EntityType]:
        """Get entity type from role"""
        if self.role:
            return self.role.entity_type
        return EntityType.HUMAN if self.is_human else EntityType.AGENT


class AccessControlService:
    """Service for building Qdrant filters based on access context"""
    
    def __init__(self, role_registry: Optional[RoleRegistry] = None):
        self.role_registry = role_registry or get_role_registry()
    
    def build_access_filter(
        self,
        context: AccessContext,
        doc_types: Optional[List[str]] = None
    ) -> Optional[Filter]:
        """
        Build Qdrant filter based on access context
        
        Args:
            context: Access context (user/agent info)
            doc_types: Optional document types filter
            
        Returns:
            Qdrant Filter object or None
        """
        must_conditions = []
        should_conditions = []
        
        # 1. Space isolation
        if context.space_id:
            must_conditions.append(
                FieldCondition(key="space_id", match=MatchValue(value=context.space_id))
            )
        
        # 2. Channel isolation (if specified)
        if context.channel_id:
            must_conditions.append(
                FieldCondition(key="channel_id", match=MatchValue(value=context.channel_id))
            )
        
        # 3. Security level
        if context.security_clearance is not None:
            # User can only see docs with security_level <= their clearance
            # Note: Qdrant doesn't have <= operator, so we use range or explicit match
            # For simplicity, we'll filter by exact match or use multiple conditions
            pass  # Implement based on your needs
        
        # 4. Visibility-based access
        visibility_conditions = []
        
        # Public documents are always visible
        visibility_conditions.append(
            FieldCondition(key="visibility", match=MatchValue(value=Visibility.PUBLIC.value))
        )
        
        # If user/agent is specified, add personalized access
        if context.is_human and context.user_id:
            # Own documents
            visibility_conditions.append(
                FieldCondition(key="owner_id", match=MatchValue(value=context.user_id))
            )
            # Explicitly shared documents
            visibility_conditions.append(
                FieldCondition(key="access_list", match=MatchAny(any=[context.user_id]))
            )
            # Team documents if user is in team
            if context.team_ids:
                visibility_conditions.append(
                    FieldCondition(key="visibility", match=MatchValue(value=Visibility.TEAM.value))
                )
            # Channel documents if channel specified
            if context.channel_id:
                visibility_conditions.append(
                    FieldCondition(key="visibility", match=MatchValue(value=Visibility.CHANNEL.value))
                )
        
        # Role-based access (using configurable roles)
        if context.role:
            role = context.role
            
            # Add role to visibility filter (document must allow this role)
            if context.is_agent:
                visibility_conditions.append(
                    FieldCondition(key="agent_roles", match=MatchAny(any=[context.role_name]))
                )
            
            # Restrict doc types based on role permissions
            if role.allowed_doc_types is not None:
                must_conditions.append(
                    FieldCondition(key="doc_type", match=MatchAny(any=role.allowed_doc_types))
                )
            
            # Check visibility levels allowed by role
            # (This is checked later in can_access_document for more fine-grained control)
        
        # 5. Document type filter
        if doc_types:
            must_conditions.append(
                FieldCondition(key="doc_type", match=MatchAny(any=doc_types))
            )
        
        # 6. Department filter
        if context.department:
            should_conditions.append(
                FieldCondition(key="department", match=MatchValue(value=context.department))
            )
            # Also allow docs without department specified (global docs)
            should_conditions.append(
                FieldCondition(key="department", match=MatchValue(value=""))
            )
        
        # Build final filter
        filter_dict = {}
        if must_conditions:
            filter_dict["must"] = must_conditions
        if visibility_conditions:
            # At least one visibility condition must match
            filter_dict["should"] = visibility_conditions
        
        return Filter(**filter_dict) if filter_dict else None
    
    def can_access_document(self, context: AccessContext, document_payload: Dict) -> bool:
        """
        Check if user/agent can access a specific document (using configurable roles)
        
        Args:
            context: Access context
            document_payload: Document payload from Qdrant
            
        Returns:
            True if access is granted
        """
        # Check space isolation
        if context.space_id and document_payload.get("space_id") != context.space_id:
            return False
        
        # Check channel isolation
        if context.channel_id and document_payload.get("channel_id") != context.channel_id:
            return False
        
        # Get role permissions
        role = context.role
        if not role:
            return False  # No role = no access
        
        # Check visibility
        visibility = document_payload.get("visibility", Visibility.PUBLIC.value)
        
        # Check if role can access this visibility level
        if not role.can_access_visibility(visibility):
            return False
        
        # Special handling for PRIVATE documents
        if visibility == Visibility.PRIVATE.value:
            # Only owner or explicitly granted users
            if context.user_id and document_payload.get("owner_id") == context.user_id:
                return True
            # Check explicit access list
            access_list = document_payload.get("access_list", [])
            if context.user_id and context.user_id in access_list:
                return True
            # Admins can access
            if role.role_name == "admin" or role.role_name == "agent_admin":
                return True
            return False
        
        # Check TEAM visibility
        if visibility == Visibility.TEAM.value:
            # Check if user is in team
            if context.team_ids and document_payload.get("team_id") in context.team_ids:
                pass  # Continue to other checks
            else:
                return False
        
        # Check explicit access list
        access_list = document_payload.get("access_list", [])
        if context.user_id and context.user_id in access_list:
            pass  # Explicitly granted, continue to other checks
        
        # Check agent role access for agents
        if context.is_agent:
            agent_roles = document_payload.get("agent_roles", [])
            if context.role_name not in agent_roles:
                # Agent role not in allowed list
                return False
        
        # Check doc type restrictions
        doc_type = document_payload.get("doc_type", "")
        if not role.can_access_doc_type(doc_type):
            return False
        
        # Check security level
        security_level = document_payload.get("security_level", 0)
        if not role.can_access_security_level(security_level):
            return False
        
        # Check department
        department = document_payload.get("department")
        if not role.can_access_department(department):
            return False
        
        return True
    
    @staticmethod
    def get_user_spaces(user_id: str) -> List[str]:
        """
        Get list of spaces user has access to
        This should query your user database/service
        """
        # TODO: Implement based on your user management system
        # Example: query PostgreSQL, MongoDB, or auth service
        return []
    
    @staticmethod
    def get_user_channels(user_id: str, space_id: str) -> List[str]:
        """
        Get list of channels user is part of in a space
        """
        # TODO: Implement based on your chat/channel system
        return []
    
    @staticmethod
    def get_user_role(user_id: str, space_id: str) -> UserRole:
        """
        Get user role in a specific space
        """
        # TODO: Implement based on your RBAC system
        return UserRole.MEMBER


# Example usage functions

def create_context_for_user(
    user_id: str,
    role_name: str,  # NEW: role name from config (e.g., "developer", "business_analyst")
    space_id: str,
    channel_id: Optional[str] = None,
    team_ids: Optional[List[str]] = None,
    department: Optional[str] = None,
) -> AccessContext:
    """
    Create access context for a human user
    
    Args:
        user_id: User ID
        role_name: Role name from configuration (e.g., "developer", "admin")
        space_id: Space ID
        channel_id: Optional channel ID
        team_ids: Teams user belongs to
        department: User's department
        
    Returns:
        AccessContext with role permissions
    """
    registry = get_role_registry()
    role = registry.get_role(role_name)
    
    if not role:
        raise ValueError(f"Role {role_name} not found in registry")
    
    if role.entity_type != EntityType.HUMAN:
        raise ValueError(f"Role {role_name} is not a human role")
    
    return AccessContext(
        user_id=user_id,
        role_name=role_name,
        space_id=space_id,
        channel_id=channel_id,
        team_ids=team_ids or [],
        department=department,
        security_clearance=role.max_security_level,
    )


def create_context_for_agent(
    agent_id: str,
    role_name: str,  # NEW: role name from config (e.g., "agent_research", "agent_support")
    space_id: str,
    channel_id: Optional[str] = None
) -> AccessContext:
    """
    Create access context for a bot agent
    
    Args:
        agent_id: Agent ID
        role_name: Role name from configuration (e.g., "agent_research", "agent_support")
        space_id: Space ID
        channel_id: Optional channel ID
        
    Returns:
        AccessContext with role permissions
    """
    registry = get_role_registry()
    role = registry.get_role(role_name)
    
    if not role:
        raise ValueError(f"Role {role_name} not found in registry")
    
    if role.entity_type != EntityType.AGENT:
        raise ValueError(f"Role {role_name} is not an agent role")
    
    return AccessContext(
        agent_id=agent_id,
        role_name=role_name,
        space_id=space_id,
        channel_id=channel_id,
        security_clearance=role.max_security_level,
    )


# Example: Augment document payload on ingestion
def augment_payload_with_access_control(
    base_payload: Dict,
    owner_id: str,
    visibility: Visibility = Visibility.TEAM,
    allowed_agent_role_names: Optional[List[str]] = None,  # NEW: role names from config
    access_list: Optional[List[str]] = None,
    security_level: int = 0,
    department: Optional[str] = None,
) -> Dict:
    """
    Augment document payload with access control metadata
    
    Args:
        base_payload: Existing payload with doc_id, space_id, etc.
        owner_id: User who uploaded the document
        visibility: Document visibility level
        allowed_agent_role_names: Which agent role names can access (e.g., ["agent_research", "agent_support"])
        access_list: Explicit user IDs with access
        security_level: Security/confidentiality level (0-5)
        department: Department this document belongs to
        
    Returns:
        Enhanced payload with access control fields
    """
    if allowed_agent_role_names is None:
        # Default: allow common agent roles
        allowed_agent_role_names = ["agent_analytics", "agent_research"]
    
    base_payload.update({
        "visibility": visibility.value,
        "owner_id": owner_id,
        "access_list": access_list or [],
        "agent_roles": allowed_agent_role_names,  # NEW: list of role names
        "security_level": security_level,
        "department": department or "",
    })
    
    return base_payload

