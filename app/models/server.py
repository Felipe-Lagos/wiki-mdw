from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Server(BaseModel):
    """
    Inventario de Servidores Físicos / Virtuales / Cloud con Repositorio de Credenciales y Plataforma.
    """
    __tablename__ = "servers"

    hostname = Column(String(100), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    secondary_ips = Column(Text, nullable=True)  # IPs adicionales o interfaces VIP / Backup
    os_name = Column(String(60), nullable=False, default="Linux")  # RHEL, Oracle Linux, AIX, Ubuntu, Windows Server
    os_version = Column(String(40), nullable=True)  # Ej: 8.8, 7.9, 2022
    environment = Column(String(20), default="PROD", nullable=False, index=True)  # PROD, QA, DEV, DR
    status = Column(String(20), default="ACTIVE", nullable=False, index=True)  # ACTIVE, MAINTENANCE, DECOMMISSIONED
    
    # Plataforma y Ubicación
    platform_type = Column(String(50), default="On-Premise", nullable=False)  # On-Premise, Cloud (AWS), Cloud (Azure), Cloud (GCP), Cloud (OCI), etc.
    location = Column(String(150), nullable=True)                             # DC Santiago - Rack B04, us-east-1, etc.

    cpu_cores = Column(Integer, nullable=True)
    ram_gb = Column(Integer, nullable=True)
    ssh_port = Column(Integer, default=22, nullable=False)
    notes = Column(Text, nullable=True)

    # Clave foránea al proyecto
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # Repositorio de Credenciales Protegido (Solo Administradores)
    auth_type = Column(String(30), default="NONE", nullable=False)   # 'PASSWORD', 'SSH_KEY', 'DOMAIN_AD', 'NONE'
    auth_username = Column(String(100), nullable=True)               # root, svc_mdw, DOMAIN\admin
    auth_secret = Column(String(255), nullable=True)                 # Contraseña o token
    ssh_key_content = Column(Text, nullable=True)                    # Repositorio de Llave Privada SSH
    domain_name = Column(String(100), nullable=True)                 # Dominio Windows Active Directory
    auth_notes = Column(Text, nullable=True)                         # Instrucciones especiales de acceso

    # Relaciones
    project = relationship("Project", back_populates="servers")
    middlewares = relationship("MiddlewareInstance", back_populates="server", cascade="all, delete-orphan")
    runbooks = relationship("RunbookCommand", back_populates="server")
    incidents = relationship("IncidentLog", back_populates="server")

    def __repr__(self):
        return f"<Server {self.hostname} ({self.ip_address}) - {self.platform_type}>"
