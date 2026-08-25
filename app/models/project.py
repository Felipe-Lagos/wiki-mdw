from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Project(BaseModel):
    """
    Proyectos o Áreas de Negocio que agrupan servidores y aplicaciones.
    Ej: 'Core Bancario', 'Canales Digitales', 'Pasarela de Pagos', 'Data Analytics'
    """
    __tablename__ = "projects"

    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)  # Ej: PRJ-CORE, PRJ-PAY
    description = Column(Text, nullable=True)
    lead_name = Column(String(100), nullable=True)  # Responsable técnico o funcional
    environment = Column(String(20), default="PROD", nullable=False)  # PROD, QA, DEV, STAGING, DR

    # Relaciones
    servers = relationship("Server", back_populates="project", cascade="all, delete-orphan")
    incidents = relationship("IncidentLog", back_populates="project")

    def __repr__(self):
        return f"<Project {self.code} - {self.name}>"
