from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class RunbookCommand(BaseModel):
    """
    Base de Conocimiento y 'Corta-Palos' (Runbook / Cheat-sheet operativo).
    Almacena procedimientos paso a paso y comandos para tareas comunes o de emergencia.
    """
    __tablename__ = "runbooks"

    title = Column(String(200), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # Ej: 'WebLogic', 'IBM MQ', 'Tomcat', 'Linux OS', 'SSL'
    description = Column(Text, nullable=True)
    command_text = Column(Text, nullable=False)  # El comando bash, script o procedimiento
    
    execution_order = Column(Integer, default=1, nullable=False)
    is_dangerous = Column(Boolean, default=False, nullable=False)  # Resaltar en rojo si es comando de impacto crítico
    requires_sudo = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(100), nullable=True)

    # Opcional: Si el corta-palos es específico para un servidor o instancia concreta
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True)
    middleware_id = Column(Integer, ForeignKey("middlewares.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relaciones
    server = relationship("Server", back_populates="runbooks")
    middleware = relationship("MiddlewareInstance", back_populates="runbooks")

    def __repr__(self):
        return f"<Runbook [{self.category}] {self.title}>"
