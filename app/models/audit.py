from sqlalchemy import Column, String, Text, Integer, JSON
from app.models.base import BaseModel


class AuditLog(BaseModel):
    """
    Log de Auditoría y Control de Cambios del Sistema.
    Registra quién, cuándo y qué cambió en cualquier entidad (servidores, corta-palos, incidentes, etc.).
    """
    __tablename__ = "audit_logs"

    entity_type = Column(String(50), nullable=False, index=True)  # 'Server', 'MiddlewareInstance', 'RunbookCommand', 'IncidentLog', 'Project'
    entity_id = Column(Integer, nullable=False, index=True)
    action = Column(String(20), nullable=False, index=True)       # 'CREATE', 'UPDATE', 'DELETE'
    
    user_name = Column(String(100), default="system", nullable=False, index=True)
    summary = Column(String(255), nullable=False)                 # Breve descripción: "Se actualizó ruta de instalación de WebLogic"
    
    old_values = Column(JSON, nullable=True)  # Snapshot JSON antes del cambio
    new_values = Column(JSON, nullable=True)  # Snapshot JSON después del cambio
    ip_address = Column(String(45), nullable=True)                # IP del cliente/operador

    @classmethod
    def log(cls, session, entity_type: str, entity_id: int, action: str, 
            summary: str, user_name: str = "system", old_values: dict = None, 
            new_values: dict = None, ip_address: str = None):
        """Método helper para registrar una entrada de auditoría de forma directa."""
        entry = cls(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action.upper(),
            user_name=user_name,
            summary=summary,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address
        )
        session.add(entry)
        return entry

    def __repr__(self):
        return f"<AuditLog [{self.action}] {self.entity_type}#{self.entity_id} by {self.user_name}>"
