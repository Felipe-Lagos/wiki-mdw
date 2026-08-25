from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.base import BaseModel


class Group(BaseModel):
    """
    Grupos de usuarios para simplificar la asignación de permisos y perfiles de acceso.
    Ej: 'Administradores MDW' (admin), 'Operadores Middleware' (editor), 'Auditores / Lectores' (viewer).
    """
    __tablename__ = "groups"

    name = Column(String(80), unique=True, nullable=False, index=True)
    code = Column(String(30), unique=True, nullable=False, index=True)  # GRP-ADMIN, GRP-OPER, GRP-VIEW
    role = Column(String(20), default="viewer", nullable=False)        # 'admin', 'editor', 'viewer'
    description = Column(Text, nullable=True)

    users = relationship("User", back_populates="group")

    def __repr__(self):
        return f"<Group {self.name} [{self.role}]>"


class User(BaseModel):
    """
    Usuarios del sistema con autenticación segura y control de roles.
    Roles:
    - 'admin'  : Acceso total (Crear, Editar, Eliminar, Ver Credenciales, Gestionar Usuarios y Rollback).
    - 'editor' : Puede Ver y Editar / Crear (Servidores, Middlewares, Corta-Palos, Bitácora), pero no eliminar ni ver credenciales.
    - 'viewer' : Solo Lectura.
    """
    __tablename__ = "users"

    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=True)
    role = Column(String(20), default="viewer", nullable=False)  # admin, editor, viewer
    is_active = Column(Boolean, default=True, nullable=False)
    
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)
    
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)

    group = relationship("Group", back_populates="users")

    def set_password(self, password: str):
        """Genera el hash seguro de la contraseña."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica la contraseña ingresada contra el hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def effective_role(self) -> str:
        """Retorna el rol más permisivo entre el asignado al usuario y el de su grupo."""
        user_role = self.role or "viewer"
        group_role = self.group.role if self.group else "viewer"
        
        role_hierarchy = {"admin": 3, "editor": 2, "viewer": 1}
        u_score = role_hierarchy.get(user_role, 1)
        g_score = role_hierarchy.get(group_role, 1)
        
        return user_role if u_score >= g_score else group_role

    @property
    def is_admin(self) -> bool:
        return self.effective_role == "admin"

    @property
    def can_edit(self) -> bool:
        return self.effective_role in ["admin", "editor"]

    @property
    def can_delete(self) -> bool:
        return self.effective_role == "admin"

    def __repr__(self):
        return f"<User {self.username} ({self.effective_role})>"
