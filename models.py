# models.py
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON as PGJSON

class Municipio(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    municipio: str
    uf: str
    edital: Optional[str] = None
    ano_edital: Optional[int] = None

    indicadores: List["Indicador"] = Relationship(
        back_populates="municipio",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

class Indicador(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    municipio_id: Optional[int] = Field(default=None, foreign_key="municipio.id")
    municipio: Optional["Municipio"] = Relationship(back_populates="indicadores")

    nome_indicador: str
    descricao: Optional[str] = None
    unidade: Optional[str] = None

    # >>> JSON no Postgres (NÃO usar str)
    tags: Optional[list] = Field(default_factory=list, sa_column=Column(PGJSON, nullable=True))
    observacoes: Optional[list] = Field(default_factory=list, sa_column=Column(PGJSON, nullable=True))
    inconsistencias: Optional[list] = Field(default_factory=list, sa_column=Column(PGJSON, nullable=True))

    formula: Optional["Formula"] = Relationship(
        back_populates="indicador",
        sa_relationship_kwargs={"uselist": False},
    )

    subindicadores: List["Subindicador"] = Relationship(
        back_populates="indicador",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    condicoes: List["Condicao"] = Relationship(
        back_populates="indicador",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

class Formula(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    indicador_id: int = Field(foreign_key="indicador.id")
    indicador: "Indicador" = Relationship(back_populates="formula")

    bruta: Optional[str] = None
    normalizada: Optional[str] = None
    hash: Optional[str] = None

class Subindicador(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    indicador_id: Optional[int] = Field(default=None, foreign_key="indicador.id")
    indicador: Optional["Indicador"] = Relationship(back_populates="subindicadores")

    nome: Optional[str] = None
    descricao: Optional[str] = None

class Condicao(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    indicador_id: Optional[int] = Field(default=None, foreign_key="indicador.id")
    indicador: Optional["Indicador"] = Relationship(back_populates="condicoes")

    regra: Optional[str] = None
    nota: Optional[float] = None
