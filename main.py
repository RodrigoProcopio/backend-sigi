from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Body
from typing import Optional, List
from models import Municipio, Indicador, Formula, Subindicador, Condicao
from database import create_db_and_tables, get_session
from sqlmodel import select
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
import json

app = FastAPI(
    title="API SIGI",
    description=(
        "API do Sistema Inteligente de Gestão de Indicadores (SIGI), "
        "utilizada para armazenar, consultar e comparar indicadores de municípios "
        "com base em editais de iluminação pública."
    ),
    version="1.0.0",
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # em produção, substitua pelo domínio do front
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# IMPORTAÇÃO DE INDICADORES
# ----------------------------------------------------------------------

@app.post(
    "/indicadores/importar",
    tags=["Indicadores"],
    description="Importa um conjunto completo de indicadores a partir de JSON (body) ou arquivo .json (campo 'file').",
)
async def importar_indicadores(
    file: UploadFile | None = File(None),
    payload: dict | None = Body(None)
):
    try:
        # Permite enviar JSON direto no body ou arquivo via multipart.
        if payload is not None:
            data = payload
        else:
            if not file:
                raise HTTPException(status_code=400, detail="Envie um arquivo .json (campo 'file') ou JSON no corpo da requisição.")
            contents = await file.read()
            data = json.loads(contents.decode("utf-8"))

        with get_session() as session:
            # evita duplicar o mesmo conjunto (município/uf/edital/ano)
            existe = session.exec(
                select(Municipio).where(
                    Municipio.municipio == data["municipio"],
                    Municipio.uf == data["uf"],
                    Municipio.edital == data.get("edital"),
                    Municipio.ano_edital == data.get("ano_edital"),
                )
            ).first()
            if existe:
                raise HTTPException(status_code=400, detail="Este conjunto de indicadores já foi importado para este município.")

            municipio = Municipio(
                municipio=data["municipio"],
                uf=data["uf"],
                edital=data.get("edital"),
                ano_edital=data.get("ano_edital"),
            )

            for i in data.get("indicadores", []):
                nome_ind = i.get("nome_indicador") or i.get("nome")
                if not nome_ind:
                    raise HTTPException(status_code=400, detail="Indicador sem 'nome_indicador'.")

                indicador = Indicador(
                    nome_indicador=nome_ind,
                    descricao=i.get("descricao"),
                    unidade=i.get("unidade"),
                    tags=i.get("tags", []),
                    observacoes=i.get("observacoes", []),
                    inconsistencias=i.get("inconsistencias", []),
                )

                if isinstance(i.get("formula"), dict):
                    indicador.formula = Formula(
                        bruta=i["formula"].get("bruta"),
                        normalizada=i["formula"].get("normalizada"),
                        hash=i["formula"].get("hash"),
                    )

                for sub in i.get("subindicadores", []):
                    indicador.subindicadores.append(
                        Subindicador(
                            nome=sub.get("nome"),
                            descricao=sub.get("descricao"),
                        )
                    )

                condicoes_raw = i.get("condicoes", [])
                if isinstance(condicoes_raw, list):
                    for cond in condicoes_raw:
                        indicador.condicoes.append(
                            Condicao(regra=cond.get("regra"), nota=cond.get("nota"))
                        )
                elif isinstance(condicoes_raw, dict):
                    for grupo in condicoes_raw.values():
                        for cond in grupo:
                            indicador.condicoes.append(
                                Condicao(regra=cond.get("regra"), nota=cond.get("nota"))
                            )

                municipio.indicadores.append(indicador)

            session.add(municipio)
            session.commit()
            session.refresh(municipio)

            return {
                "status": "sucesso",
                "mensagem": "Indicadores importados com sucesso.",
                "municipio": municipio.municipio,
                "uf": municipio.uf,
                "edital": municipio.edital,
                "ano_edital": municipio.ano_edital,
                "total_indicadores": len(municipio.indicadores),
            }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="O arquivo não está em formato JSON válido ou está malformado.")
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Campo obrigatório ausente no JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao importar os indicadores: {str(e)}")

# ----------------------------------------------------------------------
# LISTAGEM / CONSULTAS
# ----------------------------------------------------------------------

@app.get(
    "/indicadores",
    response_model=List[Municipio],
    tags=["Indicadores"],
    description="Lista todos os conjuntos de indicadores, com filtros opcionais por nome, UF, edital e ano.",
)
def listar_indicadores(
    municipio: Optional[str] = Query(None),
    uf: Optional[str] = Query(None),
    edital: Optional[str] = Query(None),
    ano_edital: Optional[int] = Query(None),
):
    with get_session() as session:
        query = select(Municipio)
        if municipio:
            query = query.where(Municipio.municipio == municipio)
        if uf:
            query = query.where(Municipio.uf == uf)
        if edital:
            query = query.where(Municipio.edital == edital)
        if ano_edital:
            query = query.where(Municipio.ano_edital == ano_edital)

        resultado = session.exec(query).all()

        if not resultado:
            filtros_aplicados = {
                "municipio": municipio,
                "uf": uf,
                "edital": edital,
                "ano_edital": ano_edital
            }
            raise HTTPException(
                status_code=404,
                detail=f"Nenhum conjunto de indicadores encontrado com os filtros fornecidos: {filtros_aplicados}"
            )

        return resultado

@app.get(
    "/indicadores/comparar",
    tags=["Indicadores"],
    description="Compara indicadores por nome (semelhança), fórmula ou hash (iguais). Apenas um critério por vez."
)
def comparar_indicadores(
    nome: Optional[str] = None,
    formula: Optional[str] = None,
    hash: Optional[str] = None
):
    filtros = [p for p in [nome, formula, hash] if p is not None]
    if len(filtros) == 0:
        raise HTTPException(status_code=400, detail="Informe um critério de comparação (nome, fórmula ou hash).")
    if len(filtros) > 1:
        raise HTTPException(status_code=400, detail="Informe apenas um critério por vez (nome, fórmula ou hash).")

    with get_session() as session:
        municipios = session.exec(select(Municipio)).all()
        equivalentes = []

        for m in municipios:
            for i in m.indicadores:
                session.refresh(i, attribute_names=["formula", "subindicadores", "condicoes"])

                match = False

                if nome and i.nome_indicador:
                    nome_user = nome.strip().lower()
                    nome_indicador = i.nome_indicador.strip().lower()
                    if nome_user in nome_indicador or nome_indicador in nome_user:
                        match = True
                elif (
                    formula and i.formula and i.formula.normalizada
                    and formula.strip().lower() == i.formula.normalizada.strip().lower()
                ):
                    match = True
                elif hash and i.formula and i.formula.hash == hash:
                    match = True

                if match:
                    equivalentes.append({
                        "id": i.id,
                        "municipio": m.municipio,
                        "uf": m.uf,
                        "nome_indicador": i.nome_indicador,
                        "descricao": i.descricao,
                        "unidade": i.unidade,
                        "tags": i.tags or [],
                        "observacoes": i.observacoes or [],
                        "inconsistencias": i.inconsistencias or [],

                        "formula": {
                            "bruta": i.formula.bruta if i.formula else None,
                            "normalizada": i.formula.normalizada if i.formula else None,
                            "hash": i.formula.hash if i.formula else None,
                        } if i.formula else None,
                        "subindicadores": [
                            {"nome": s.nome, "descricao": s.descricao} for s in i.subindicadores
                        ],
                        "condicoes": [
                            {"regra": c.regra, "nota": c.nota} for c in i.condicoes
                        ]
                    })

        if not equivalentes:
            return JSONResponse(
                status_code=404,
                content={"mensagem": "Nenhum indicador corresponde à pesquisa."}
            )

        return equivalentes

@app.get(
    "/indicadores/semelhantes",
    tags=["Indicadores"],
    description="Retorna grupos de indicadores semelhantes com base em hash ou fórmula normalizada."
)
def indicadores_semelhantes(criterio: str = Query(..., enum=["hash", "formula"])):
    try:
        with get_session() as session:
            if criterio == "hash":
                subq = (
                    session.query(Formula.hash, func.count(Formula.id).label("total"))
                    .filter(Formula.hash.isnot(None))
                    .group_by(Formula.hash)
                    .having(func.count(Formula.id) > 1)
                    .subquery()
                )
                formulas = session.query(Formula).join(subq, Formula.hash == subq.c.hash).all()
                agrupador = lambda f: f.hash
            else:
                subq = (
                    session.query(Formula.normalizada, func.count(Formula.id).label("total"))
                    .filter(Formula.normalizada.isnot(None))
                    .group_by(Formula.normalizada)
                    .having(func.count(Formula.id) > 1)
                    .subquery()
                )
                formulas = session.query(Formula).join(subq, Formula.normalizada == subq.c.normalizada).all()
                agrupador = lambda f: f.normalizada

            grupos = {}

            for formula in formulas:
                chave = agrupador(formula)
                if chave not in grupos:
                    grupos[chave] = []

                # 1:1 - pega o indicador pelo FK da fórmula
                ind = session.get(Indicador, formula.indicador_id)
                if ind:
                    m = session.get(Municipio, ind.municipio_id)
                    session.refresh(ind, attribute_names=["subindicadores", "condicoes"])
                    grupos[chave].append({
                        "id": ind.id,
                        "nome_indicador": ind.nome_indicador,
                        "descricao": ind.descricao,
                        "municipio": m.municipio if m else None,
                        "uf": m.uf if m else None,
                        "formula": {
                            "bruta": formula.bruta,
                            "normalizada": formula.normalizada,
                            "hash": formula.hash
                        }
                    })

            return grupos

    except Exception as e:
        print("Erro ao buscar indicadores semelhantes:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/indicadores/por-municipio",
    tags=["Indicadores"],
    description="Retorna todos os indicadores de um município informado (busca parcial e case-insensitive)."
)
def indicadores_por_municipio(nome: str = Query(..., description="Nome (ou parte do nome) do município")):
    with get_session() as session:
        municipio = session.exec(
            select(Municipio).where(Municipio.municipio.ilike(f"%{nome}%"))
        ).first()

        if not municipio:
            raise HTTPException(status_code=404, detail=f"Nenhum município encontrado contendo '{nome}'.")

        session.refresh(municipio, attribute_names=["indicadores"])
        resultado = []

        for i in municipio.indicadores:
            session.refresh(i, attribute_names=["formula", "subindicadores", "condicoes"])
            resultado.append({
                "id": i.id,
                "nome_indicador": i.nome_indicador,
                "descricao": i.descricao,
                "unidade": i.unidade,
                "tags": i.tags or [],
                "observacoes": i.observacoes or [],
                "inconsistencias": i.inconsistencias or [],
                "formula": {
                    "bruta": i.formula.bruta if i.formula else None,
                    "normalizada": i.formula.normalizada if i.formula else None,
                    "hash": i.formula.hash if i.formula else None,
                } if i.formula else None,
                "subindicadores": [
                    {"nome": s.nome, "descricao": s.descricao} for s in i.subindicadores
                ],
                "condicoes": [
                    {"regra": c.regra, "nota": c.nota} for c in i.condicoes
                ]
            })

        return {
            "municipio": municipio.municipio,
            "uf": municipio.uf,
            "total_indicadores": len(resultado),
            "indicadores": resultado
        }

# ----------------------------------------------------------------------
# CRUD BÁSICO
# ----------------------------------------------------------------------

@app.get(
    "/indicadores/{id}",
    response_model=Municipio,
    tags=["Indicadores"],
    description="Retorna um conjunto de indicadores por ID."
)
def obter_indicador(id: int):
    with get_session() as session:
        m = session.get(Municipio, id)
        if not m:
            raise HTTPException(status_code=404, detail="Não encontrado")
        return m

@app.put(
    "/indicadores/{id}",
    response_model=Municipio,
    tags=["Indicadores"],
    description="Atualiza completamente um conjunto de indicadores existente."
)
def atualizar_indicador(id: int, dados: Municipio):
    with get_session() as session:
        m = session.get(Municipio, id)
        if not m:
            raise HTTPException(status_code=404, detail=f"Conjunto de indicadores com ID {id} não encontrado.")

        dados.id = id
        session.merge(dados)
        session.commit()
        return {
            "status": "sucesso",
            "mensagem": f"Conjunto de indicadores '{dados.municipio}' (ID {id}) atualizado com sucesso.",
            "dados_atualizados": dados
        }

@app.delete(
    "/indicadores/{id}",
    tags=["Indicadores"],
    description="Remove um conjunto completo de indicadores pelo ID."
)
def excluir_indicador(id: int):
    with get_session() as session:
        m = session.get(Municipio, id)
        if not m:
            raise HTTPException(status_code=404, detail=f"Indicador com ID {id} não encontrado.")
        nome = m.municipio
        session.delete(m)
        session.commit()
        return {
            "status": "sucesso",
            "mensagem": f"Indicador '{nome}' (ID {id}) deletado com sucesso."
        }

@app.delete(
    "/indicadores",
    tags=["Indicadores"],
    description="Exclui todos os conjuntos de indicadores. CUIDADO: essa operação é irreversível."
)
def excluir_todos_indicadores():
    with get_session() as session:
        municipios = session.exec(select(Municipio)).all()
        total = len(municipios)
        if total == 0:
            return {"status": "nenhuma ação", "mensagem": "Nenhum conjunto de indicadores encontrado para exclusão."}
        for m in municipios:
            session.delete(m)
        session.commit()
        return {
            "status": "sucesso",
            "mensagem": f"Todos os {total} conjuntos de indicadores foram deletados com sucesso."
        }

# ----------------------------------------------------------------------
# EDIÇÃO DE ATRIBUTOS
# ----------------------------------------------------------------------

@app.patch(
    "/indicadores/{id}/formula",
    tags=["Indicadores"],
    description="Atualiza parcialmente a fórmula (bruta, normalizada e hash) de um indicador."
)
def atualizar_formula(id: int, bruta: Optional[str] = None, normalizada: Optional[str] = None, hash: Optional[str] = None):
    with get_session() as session:
        indicador = session.get(Indicador, id)
        if not indicador:
            raise HTTPException(status_code=404, detail=f"Indicador com ID {id} não encontrado.")
        if not indicador.formula:
            raise HTTPException(status_code=400, detail=f"O indicador '{indicador.nome_indicador}' não possui fórmula associada.")

        if bruta is not None:
            indicador.formula.bruta = bruta
        if normalizada é not None:
            indicador.formula.normalizada = normalizada
        if hash is not None:
            indicador.formula.hash = hash

        session.add(indicador.formula)
        session.commit()
        return {
            "status": "sucesso",
            "mensagem": f"Fórmula do indicador '{indicador.nome_indicador}' (ID {indicador.id}) atualizada com sucesso."
        }

@app.put(
    "/indicadores/{id}/tags",
    tags=["Indicadores"],
    description="Substitui completamente a lista de tags de um indicador."
)
def atualizar_tags(id: int, tags: List[str]):
    with get_session() as session:
        indicador = session.get(Indicador, id)
        if not indicador:
            raise HTTPException(status_code=404, detail=f"Indicador com ID {id} não encontrado.")

        # agora é JSON no Postgres: atribuir lista Python diretamente
        indicador.tags = tags
        session.add(indicador)
        session.commit()

        return {
            "status": "sucesso",
            "mensagem": f"Tags do indicador '{indicador.nome_indicador}' (ID {indicador.id}) atualizadas com sucesso.",
            "tags_aplicadas": tags
        }

@app.get(
    "/indicadores/exportar/{id}",
    tags=["Indicadores"],
    description="Exporta um conjunto de indicadores completo em formato JSON estruturado."
)
def exportar_indicadores(id: int):
    with get_session() as session:
        municipio = session.get(Municipio, id)
        if not municipio:
            raise HTTPException(status_code=404, detail="Município não encontrado")

        session.refresh(municipio, attribute_names=["indicadores"])

        indicadores_data = []
        for indicador in municipio.indicadores:
            session.refresh(indicador, attribute_names=["formula", "subindicadores", "condicoes"])

            indicador_json = {
                "nome_indicador": indicador.nome_indicador,
                "descricao": indicador.descricao,
                "unidade": indicador.unidade,
                "tags": indicador.tags or [],
                "observacoes": indicador.observacoes or [],
                "inconsistencias": indicador.inconsistencias or [],
                "formula": {
                    "bruta": indicador.formula.bruta if indicador.formula else None,
                    "normalizada": indicador.formula.normalizada if indicador.formula else None,
                    "hash": indicador.formula.hash if indicador.formula else None,
                } if indicador.formula else None,
                "subindicadores": [
                    {"nome": s.nome, "descricao": s.descricao} for s in indicador.subindicadores
                ],
                "condicoes": [
                    {"regra": c.regra, "nota": c.nota} for c in indicador.condicoes
                ]
            }

            indicadores_data.append(indicador_json)

        resultado = {
            "municipio": municipio.municipio,
            "uf": municipio.uf,
            "edital": municipio.edital,
            "ano_edital": municipio.ano_edital,
            "indicadores": indicadores_data
        }

        return JSONResponse(content=resultado)
