from __future__ import annotations

from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column
from sqlalchemy.types import JSON, Float, Text


# =========================
# Tabelas
# =========================

class Municipio(SQLModel, table=True):
    __tablename__ = "municipio"

    id: Optional[int] = Field(default=None, primary_key=True)
    municipio: str = Field(index=True, min_length=1, description="Nome do município (ex.: Itanhaém)")
    uf: str = Field(min_length=2, max_length=2, description="UF (ex.: SP)")
    edital: Optional[str] = Field(default=None, description="Identificação do edital (ex.: 001/2023)")
    ano_edital: Optional[int] = Field(default=None, description="Ano do edital (ex.: 2023)")

    # Relacionamentos
    indicadores: List[Indicador] = Relationship(back_populates="municipio")

    def __repr__(self) -> str:
        return f"<Municipio id={self.id} {self.municipio}/{self.uf} edital={self.edital}>"


class Formula(SQLModel, table=True):
    __tablename__ = "formula"

    id: Optional[int] = Field(default=None, primary_key=True)
    indicador_id: int = Field(foreign_key="indicador.id", unique=True, index=True)

    # Campos conforme padrão do SIGI
    bruta: Optional[str] = Field(default=None, sa_column=Column(Text), description="Fórmula conforme o edital")
    normalizada: Optional[str] = Field(default=None, sa_column=Column(Text), description="Fórmula normalizada (tokenizada)")
    hash: Optional[str] = Field(default=None, index=True, description="Hash estável da fórmula normalizada")

    # Relacionamento 1-1 com Indicador
    indicador: "Indicador" = Relationship(back_populates="formula")

    def __repr__(self) -> str:
        return f"<Formula indicador_id={self.indicador_id} hash={self.hash}>"


class Subindicador(SQLModel, table=True):
    __tablename__ = "subindicador"

    id: Optional[int] = Field(default=None, primary_key=True)
    indicador_id: int = Field(foreign_key="indicador.id", index=True)

    nome: str = Field(min_length=1, description="Nome do subindicador (ex.: 'Disponibilidade de Ponto')")
    descricao: Optional[str] = Field(default=None, sa_column=Column(Text))
    unidade: Optional[str] = Field(default=None, description="Unidade do subindicador (ex.: %, h, un)")

    indicador: "Indicador" = Relationship(back_populates="subindicadores")

    def __repr__(self) -> str:
        return f"<Subindicador id={self.id} indicador_id={self.indicador_id} nome={self.nome}>"


class Condicao(SQLModel, table=True):
    __tablename__ = "condicao"

    id: Optional[int] = Field(default=None, primary_key=True)
    indicador_id: int = Field(foreign_key="indicador.id", index=True)

    # Regra/escoring (mantém flexibilidade para os diversos formatos dos editais)
    regra: Optional[str] = Field(default=None, sa_column=Column(Text), description="Texto/regra de pontuação")
    nota: Optional[float] = Field(default=None, sa_column=Column(Float), description="Nota/peso aplicado (se houver)")

    indicador: "Indicador" = Relationship(back_populates="condicoes")

    def __repr__(self) -> str:
        return f"<Condicao id={self.id} indicador_id={self.indicador_id} nota={self.nota}>"


class Indicador(SQLModel, table=True):
    __tablename__ = "indicador"

    id: Optional[int] = Field(default=None, primary_key=True)
    municipio_id: int = Field(foreign_key="municipio.id", index=True)

    # Campos principais
    nome_indicador: str = Field(min_length=1, index=True)
    descricao: Optional[str] = Field(default=None, sa_column=Column(Text))
    unidade: Optional[str] = Field(default=None, description="Unidade do indicador (ex.: %)")

    # Campos compostos (listas) — armazenados como JSON
    tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Lista de tags (ex.: ['disponibilidade','luminosidade'])",
    )
    observacoes: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Observações diversas do edital",
    )
    inconsistencias: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Inconsistências identificadas",
    )

    # Relacionamentos
    municipio: Municipio = Relationship(back_populates="indicadores")
    formula: Optional[Formula] = Relationship(
        back_populates="indicador",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )
    subindicadores: List[Subindicador] = Relationship(
        back_populates="indicador",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    condicoes: List[Condicao] = Relationship(
        back_populates="indicador",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    def __repr__(self) -> str:
        return f"<Indicador id={self.id} nome={self.nome_indicador} municipio_id={self.municipio_id}>"
