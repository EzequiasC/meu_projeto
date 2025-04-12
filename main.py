from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from functools import lru_cache
import wikipedia
import requests

# Inicialização do FastAPI
app = FastAPI()

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite acesso de qualquer origem
    allow_credentials=True,
    allow_methods=["*"],  # Permite qualquer método
    allow_headers=["*"],  # Permite qualquer cabeçalho
)

# Montando os arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Modelos de dados
class AutorInfo(BaseModel):
    nome: str

class ObraInfo(BaseModel):
    titulo: str
    autor: str | None = None  # autor opcional para buscas mais flexíveis

# Funções de busca com cache
@lru_cache(maxsize=100)
def buscar_biografia(nome: str) -> str:
    wikipedia.set_lang("pt")
    try:
        return wikipedia.summary(nome, sentences=5)
    except wikipedia.exceptions.DisambiguationError:
        return "Biografia ambígua, não encontrada claramente."
    except wikipedia.exceptions.HTTPTimeoutError:
        return "Erro ao acessar Wikipedia."
    except Exception:
        return "Biografia não disponível."

@lru_cache(maxsize=100)
def buscar_imagem_autor(nome: str) -> str:
    wikipedia.set_lang("pt")
    try:
        page = wikipedia.page(nome)
        # A imagem do autor geralmente está no infobox da página
        imagem_url = page.images[0]  # Vamos pegar a primeira imagem
        return imagem_url
    except wikipedia.exceptions.DisambiguationError:
        return None
    except wikipedia.exceptions.HTTPTimeoutError:
        return None
    except Exception as e:
        return None

@lru_cache(maxsize=100)
def buscar_obras(nome: str) -> list:
    url = f"https://openlibrary.org/search.json?author={nome}"
    try:
        resposta = requests.get(url).json()
    except requests.exceptions.RequestException:
        return ["Erro ao buscar obras"]
    
    obras = []
    for doc in resposta["docs"][:5]:  # Limita a 5 principais
        obras.append(doc.get("title", "Título Desconhecido"))
    return obras

@lru_cache(maxsize=100)
def buscar_obra_por_titulo(titulo: str) -> dict:
    wikipedia.set_lang("pt")
    url = f"https://openlibrary.org/search.json?title={titulo}"
    try:
        resposta = requests.get(url).json()
    except requests.exceptions.RequestException:
        return {"erro": "Erro ao acessar o OpenLibrary"}

    if resposta["docs"]:
        doc = resposta["docs"][0]
        titulo = doc.get("title", "Desconhecido")
        autor = doc.get("author_name", ["Desconhecido"])[0]
        ano_publicacao = doc.get("first_publish_year", "Desconhecido")
        nota = doc.get("ratings_average", "Sem nota")

        # Pega a capa do livro
        cover_id = doc.get("cover_i")
        imagem_capa = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None

        # Tenta buscar resumo com base no título via Wikipedia
        try:
            resumo = wikipedia.summary(titulo, sentences=3)
        except:
            resumo = "Resumo não disponível."

        return {
            "titulo": titulo,
            "autor": autor,
            "ano_publicacao": ano_publicacao,
            "nota": nota,
            "descricao": resumo,
            "capa": imagem_capa
        }
    else:
        return {"mensagem": "Obra não encontrada"}

# Endpoint principal para servir a página HTML
@app.get("/", response_class=HTMLResponse)
async def tela_principal(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Endpoint para obter informações sobre o autor
@app.post("/autor")
def obter_info_autor(autor: AutorInfo):
    nome = autor.nome
    try:
        resumo = buscar_biografia(nome)
        obras = buscar_obras(nome)
        imagem = buscar_imagem_autor(nome)
        return {
            "autor": nome,
            "biografia": resumo,
            "imagem": imagem or "https://via.placeholder.com/150",  # Imagem padrão caso não haja imagem do autor
            "obras_principais": obras
        }
    except Exception as e:
        return {"erro": str(e)}

# Endpoint para obter informações sobre a obra
@app.post("/obra")
def obter_info_obra(obra: ObraInfo):
    try:
        if obra.autor:
            # Se o autor for informado, busca pela combinação de título e autor
            resultado = buscar_obra_por_titulo(obra.titulo)
        else:
            # Se o autor não for informado, busca apenas pelo título
            resultado = buscar_obra_por_titulo(obra.titulo)
        return resultado
    except Exception as e:
        return {"erro": str(e)}
