from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime
from app.database import Base


class BaseModel(Base):
    """
    Clase base abstracta con campos de auditoría estándar y métodos de serialización.
    """
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc), 
        nullable=False
    )

    def to_dict(self, exclude=None):
        """Convierte las columnas del modelo en un diccionario serializable."""
        exclude = set(exclude or [])
        result = {}
        for column in self.__table__.columns:
            if column.name in exclude:
                continue
            val = getattr(self, column.name)
            if isinstance(val, datetime):
                val = val.isoformat()
            result[column.name] = val
        return result
