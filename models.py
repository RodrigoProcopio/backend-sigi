# models.py
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


# -----------------------------
# MUNICÍPIO
# -----------------------------
class Municipio(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    municipio: str
    uf: str
    edital: Optional[str] = None
    ano_edital: Optional[int] = None

    # 1:N Município -> Indicadores
    indicadores: List["Indicador"] = Relationship(
        back_populates="municipio",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


# -----------------------------
# FORMULA (opcional por indicador)
# -----------------------------
class Formula(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bruta: Optional[str] = None
    normalizada: Optional[str] = None
    hash: Optional[str] = None

    # relação inversa 1:1 ou 1:N (conforme seu uso)
    indicador: Optional["Indicador"] = Relationship(back_populates="formula")


# -----------------------------
# INDICADOR
# -----------------------------
class Indicador(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    municipio_id: Optional[int] = Field(default=None, foreign_key="municipio.id")
    municipio: Optional["Municipio"] = Relationship(back_populates="indicadores")

    nome_indicador: str
    descricao: Optional[str] = None
    unidade: Optional[str] = None

    # guardados como JSON serializado (string)
    tags: Optional[str] = None
    observacoes: Optional[str] = None
    inconsistencias: Optional[str] = None

    # relação com fórmula (FK em Indicador)
    formula_id: Optional[int] = Field(default=None, foreign_key="formula.id")
    formula: Optional["Formula"] = Relationship(back_populates="indicador")

    # 1:N Indicador -> Subindicadores / Condicoes
    subindicadores: List["Subindicador"] = Relationship(
        back_populates="indicador",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    condicoes: List["Condicao"] = Relationship(
        back_populates="indicador",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


# -----------------------------
# SUBINDICADOR
# -----------------------------
class Subindicador(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    indicador_id: Optional[int] = Field(default=None, foreign_key="indicador.id")
    indicador: Optional["Indicador"] = Relationship(back_populates="subindicadores")

    nome: Optional[str] = None
    descricao: Optional[str] = None


# -----------------------------
# CONDICAO (faixas/nota)
# -----------------------------
class Condicao(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    indicador_id: Optional[int] = Field(default=None, foreign_key="indicador.id")
    indicador: Optional["Indicador"] = Relationship(back_populates="condicoes")

    regra: Optional[str] = None
    nota: Optional[float] = None
