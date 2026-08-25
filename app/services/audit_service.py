from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from app.models.server import Server
from app.models.middleware import MiddlewareInstance
from app.models.runbook import RunbookCommand
from app.models.incident import IncidentLog
from app.models.project import Project

MODEL_MAP = {
    "Server": Server,
    "MiddlewareInstance": MiddlewareInstance,
    "RunbookCommand": RunbookCommand,
    "IncidentLog": IncidentLog,
    "Project": Project
}


class AuditService:
    """
    Servicio centralizado para registrar eventos de auditoría, control de versiones y reversión (Rollback).
    """

    @staticmethod
    def calculate_diff(old_dict: Dict[str, Any], new_dict: Dict[str, Any], ignore_keys: set = None) -> Dict[str, Dict[str, Any]]:
        """
        Compara dos diccionarios y retorna únicamente las claves que cambiaron con sus valores anteriores y nuevos.
        """
        if ignore_keys is None:
            ignore_keys = {"created_at", "updated_at"}

        diff = {}
        all_keys = set(old_dict.keys()).union(set(new_dict.keys())) - ignore_keys

        for key in all_keys:
            old_val = old_dict.get(key)
            new_val = new_dict.get(key)
            if old_val != new_val:
                diff[key] = {
                    "old": old_val,
                    "new": new_val
                }
        return diff

    @classmethod
    def log_change(
        cls,
        session: Session,
        entity_type: str,
        entity_id: int,
        action: str,
        summary: str,
        user_name: str = "sysadmin",
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Inserta un registro de auditoría en la base de datos.
        """
        return AuditLog.log(
            session=session,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action.upper(),
            summary=summary,
            user_name=user_name,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address
        )

    @classmethod
    def rollback_change(cls, session: Session, audit_id: int, user_name: str = "sysadmin", ip_address: str = None) -> Tuple[bool, str]:
        """
        Revierte los cambios de una entidad restaurando los valores de su snapshot 'old_values'.
        """
        audit_entry = session.query(AuditLog).filter(AuditLog.id == audit_id).first()
        if not audit_entry:
            return False, "Registro de auditoría no encontrado."

        if not audit_entry.old_values:
            return False, "No existe un estado anterior disponible (old_values) para revertir."

        model_class = MODEL_MAP.get(audit_entry.entity_type)
        if not model_class:
            return False, f"Tipo de entidad '{audit_entry.entity_type}' no soportado para reversión."

        entity = session.query(model_class).filter(model_class.id == audit_entry.entity_id).first()
        if not entity:
            return False, f"La entidad {audit_entry.entity_type} #{audit_entry.entity_id} ya no existe."

        current_values = entity.to_dict()
        old_data = audit_entry.old_values

        # Restaurar campos
        ignore_fields = {"id", "created_at", "updated_at"}
        for key, val in old_data.items():
            if key not in ignore_fields and hasattr(entity, key):
                setattr(entity, key, val)

        session.flush()
        restored_values = entity.to_dict()

        # Registrar la acción de Rollback en la auditoría
        cls.log_change(
            session=session,
            entity_type=audit_entry.entity_type,
            entity_id=entity.id,
            action="ROLLBACK",
            summary=f"Reversión exitosa a la versión previa a la Auditoría #{audit_id}",
            user_name=user_name,
            old_values=current_values,
            new_values=restored_values,
            ip_address=ip_address
        )

        return True, f"Se restauró exitosamente {audit_entry.entity_type} #{entity.id} a su estado anterior."
